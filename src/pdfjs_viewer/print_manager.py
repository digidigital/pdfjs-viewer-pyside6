"""Print process manager for isolated print dialog handling.

This module manages the lifecycle of the separate print process, including:
- Process spawning and shutdown
- IPC communication via QLocalSocket/QLocalServer
- Error recovery and timeout handling
- Resource cleanup
"""

import logging
import os
import sys
import json
import tempfile
import uuid
from typing import Optional, Dict, Any
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QProcess, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger(__name__)

# Environment variable used as sentinel for the print subprocess in frozen apps.
_FROZEN_PRINT_PROCESS_ENV_VAR = '_PDFJS_PRINT_PROCESS'

# Set to True once freeze_support() has been called by the application.
_freeze_support_called = False


def freeze_support():
    """Enable PyInstaller support for the QT_DIALOG print handler.

    Call this at the very beginning of your application's entry point,
    **before** creating ``QApplication``, when using the ``QT_DIALOG``
    print handler with PyInstaller (both ``--onefile`` and ``--onedir``).

    This is only needed for ``PrintHandler.QT_DIALOG``.  The ``SYSTEM``
    and ``EMIT_SIGNAL`` handlers do not require this call.

    The function is safe to call in non-frozen environments — it returns
    immediately if the application is not running under PyInstaller.

    Example::

        import pdfjs_viewer

        def main():
            pdfjs_viewer.freeze_support()   # before QApplication
            app = QApplication(sys.argv)
            ...

        if __name__ == '__main__':
            main()
    """
    global _freeze_support_called

    if not getattr(sys, 'frozen', False):
        return

    sentinel = os.environ.get(_FROZEN_PRINT_PROCESS_ENV_VAR)
    if sentinel is None:
        # Normal application launch — just mark that we were called.
        _freeze_support_called = True
        return

    # ----- This IS the print subprocess invocation. -----
    # Remove the sentinel so it does not propagate to further children.
    del os.environ[_FROZEN_PRINT_PROCESS_ENV_VAR]

    from .print_process.main import main as print_main

    print_main()
    sys.exit(0)


class PrintManager(QObject):
    """Manages print process lifecycle and IPC communication.

    This class handles:
    - Spawning the print process
    - IPC via QLocalSocket
    - Timeout handling
    - Error recovery
    - Resource cleanup
    """

    # Signals
    print_completed = Signal(bool, str)  # success, message
    error_occurred = Signal(str)  # error_message

    def __init__(self, parent: Optional[QObject] = None):
        """Initialize print manager.

        Args:
            parent: Parent QObject
        """
        super().__init__(parent)
        self._process: Optional[QProcess] = None
        self._server: Optional[QLocalServer] = None
        self._socket: Optional[QLocalSocket] = None
        self._socket_name: Optional[str] = None
        self._timeout_timer: Optional[QTimer] = None
        self._temp_pdf_path: Optional[str] = None
        self._response_buffer = bytearray()
        self._is_cleaning_up = False  # Prevent multiple cleanup calls

    def show_print_dialog_and_print(
        self,
        pdf_data: bytes,
        total_pages: int,
        timeout_ms: int = 300000,  # 5 minutes default
        print_dpi: int = 300,
        print_fit_to_page: bool = True,
        print_parallel_pages: int = 0  # Deprecated, ignored
    ) -> None:
        """Show print dialog in separate process and execute print if accepted.

        This is a non-blocking operation. Results are emitted via signals:
        - print_completed(success, message) when done
        - error_occurred(error_msg) on error

        Args:
            pdf_data: PDF file bytes
            total_pages: Total number of pages
            timeout_ms: Timeout in milliseconds (default 5 minutes)
            print_dpi: DPI for rendering (default 300)
            print_fit_to_page: Scale to fit page (default True)
            print_parallel_pages: Deprecated, ignored (printing is now sequential)
        """
        # Deprecation warning
        if print_parallel_pages != 0 and print_parallel_pages != 1:
            print(
                "DeprecationWarning: print_parallel_pages is deprecated and ignored. "
                "Printing is now sequential for better stability."
            )

        # Store config for later use in request
        self._print_config = {
            'dpi': print_dpi,
            'fit_to_page': print_fit_to_page,
            'parallel_pages': 1  # Always 1, sequential
        }
        try:
            # Reset cleanup flag for new operation
            self._is_cleaning_up = False

            # Generate unique socket name
            self._socket_name = f"pdfjs_print_{uuid.uuid4().hex[:8]}"

            # Write PDF data to temp file BEFORE starting the process.
            # waitForStarted() pumps the event loop, so the subprocess
            # could connect and trigger _on_new_connection before we
            # return.  _pending_request and the temp file must be ready
            # by then.
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            try:
                tmp.write(pdf_data)
            finally:
                tmp.close()
            self._temp_pdf_path = tmp.name

            self._pending_request = {
                'command': 'show_and_print',
                'total_pages': total_pages,
                'pdf_file': self._temp_pdf_path,
                'print_config': self._print_config
            }

            # Create IPC server
            self._server = QLocalServer(self)
            if not self._server.listen(self._socket_name):
                self.error_occurred.emit(f"Failed to create IPC server: {self._server.errorString()}")
                return

            # Wait for connection
            self._server.newConnection.connect(self._on_new_connection)

            # Start print process
            self._process = QProcess(self)
            self._process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
            self._process.readyReadStandardError.connect(self._on_stderr_ready)
            self._process.finished.connect(self._on_process_finished)
            self._process.errorOccurred.connect(self._on_process_error)

            # Get command (PyInstaller compatible)
            executable, args = self._get_print_process_command()

            # In frozen builds, set a sentinel env var so that
            # freeze_support() in the child process enters the
            # print-process code path instead of starting the GUI.
            # Also clean PyInstaller's library path overrides.
            if getattr(sys, 'frozen', False):
                from PySide6.QtCore import QProcessEnvironment
                env = QProcessEnvironment.systemEnvironment()
                env.insert(_FROZEN_PRINT_PROCESS_ENV_VAR, '1')
                for var in ('LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH',
                            'DYLD_FRAMEWORK_PATH'):
                    orig_key = f'{var}_ORIG'
                    if env.contains(orig_key):
                        orig_val = env.value(orig_key, '')
                        if orig_val:
                            env.insert(var, orig_val)
                        else:
                            env.remove(var)
                        env.remove(orig_key)
                    elif env.contains(var):
                        env.remove(var)
                self._process.setProcessEnvironment(env)

            self._process.start(executable, args)

            if not self._process.waitForStarted(5000):
                self.error_occurred.emit(f"Failed to start print process: {self._process.errorString()}")
                self._cleanup()
                return

            # Set up timeout
            self._timeout_timer = QTimer(self)
            self._timeout_timer.setSingleShot(True)
            self._timeout_timer.timeout.connect(self._on_timeout)
            self._timeout_timer.start(timeout_ms)

        except Exception as e:
            self.error_occurred.emit(f"Failed to initialize print process: {str(e)}")
            self._cleanup()

    def _get_print_process_command(self) -> tuple:
        """Get command to run print process (PyInstaller compatible).

        In frozen environments (both onefile and onedir), the executable is
        re-launched with a sentinel environment variable that causes
        ``freeze_support()`` in the application entry point to branch into
        the print-process code path instead of starting the GUI.

        In a normal Python environment, ``python -m pdfjs_viewer.print_process``
        is used.
        """     
        if getattr(sys, 'frozen', False):
            if not _freeze_support_called:
                logger.warning(
                    "pdfjs_viewer.freeze_support() was not called. "
                    "QT_DIALOG print handler will not work correctly in "
                    "frozen apps.  Add pdfjs_viewer.freeze_support() at "
                    "the start of your main()."
                )
            # Point to frozen executable    
            executable = sys.executable
            
            # If frozen and in AppImage point to AppImage
            appimage = os.environ.get('APPIMAGE')
            if appimage:
                executable = appimage
            
            return (executable, [self._socket_name])
        else:
            return (sys.executable, ['-m', 'pdfjs_viewer.print_process', self._socket_name])

    def _on_new_connection(self):
        """Handle new connection from print process."""
        if not self._server:
            return

        self._socket = self._server.nextPendingConnection()
        if not self._socket:
            return

        # Connect signals
        self._socket.readyRead.connect(self._on_ready_read)
        self._socket.disconnected.connect(self._on_disconnected)

        # Send request
        try:
            request_data = json.dumps(self._pending_request).encode('utf-8')
            self._socket.write(request_data)
            self._socket.flush()
        except Exception as e:
            self.error_occurred.emit(f"Failed to send request: {str(e)}")
            self._cleanup()

    # Maximum response buffer size (10 MB) to prevent memory exhaustion
    MAX_RESPONSE_BUFFER_SIZE = 10 * 1024 * 1024

    def _on_ready_read(self):
        """Handle data received from print process."""
        if not self._socket:
            return

        try:
            # Read all available data
            new_data = self._socket.readAll().data()

            # Check buffer size limit to prevent memory exhaustion
            if len(self._response_buffer) + len(new_data) > self.MAX_RESPONSE_BUFFER_SIZE:
                self.error_occurred.emit("Response buffer exceeded maximum size")
                self._cleanup()
                return

            self._response_buffer.extend(new_data)

            # Try to parse as JSON
            try:
                response = json.loads(self._response_buffer.decode('utf-8'))
                self._response_buffer.clear()  # Clear buffer after successful parse
                self._handle_response(response)
            except json.JSONDecodeError:
                # Not complete yet, wait for more data
                pass

        except Exception as e:
            self.error_occurred.emit(f"Error reading response: {str(e)}")
            self._cleanup()

    def _handle_response(self, response: Dict[str, Any]):
        """Handle response from print process.

        Args:
            response: Response dictionary from print process
        """
        try:
            status = response.get('status')

            if status == 'error':
                error_msg = response.get('error', 'Unknown error')
                traceback = response.get('traceback', '')
                full_error = f"{error_msg}\n{traceback}" if traceback else error_msg
                self.error_occurred.emit(full_error)
                self._cleanup()
                return

            elif status == 'ok':
                # Check if user cancelled dialog
                dialog_result = response.get('dialog_result')
                if dialog_result and not dialog_result.get('accepted'):
                    # User cancelled
                    self.print_completed.emit(False, 'Print cancelled by user')
                    self._cleanup()
                    return

                # Check print result
                print_result = response.get('print_result')
                if print_result:
                    success = print_result.get('success', False)
                    if success:
                        message = print_result.get('message', 'Print completed successfully')
                        self.print_completed.emit(True, message)
                    else:
                        error = print_result.get('error') or 'Print failed'
                        self.error_occurred.emit(error)
                else:
                    # No print result (user cancelled)
                    self.print_completed.emit(False, 'Print cancelled')

                self._cleanup()

            else:
                self.error_occurred.emit(f"Unknown response status: {status}")
                self._cleanup()

        except Exception as e:
            self.error_occurred.emit(f"Error handling response: {str(e)}")
            self._cleanup()

    def _on_disconnected(self):
        """Handle socket disconnection."""
        # Process finished normally, cleanup will happen in _on_process_finished
        pass

    def _on_process_finished(self, exit_code: int, exit_status):
        """Handle process termination.

        Args:
            exit_code: Process exit code
            exit_status: QProcess exit status
        """
        # The subprocess has exited.  Any data it wrote to the socket
        # is now fully buffered on our side.  Drain it before cleanup
        # destroys the socket.
        self._drain_socket()

        # Read stderr for diagnostics regardless of exit code.
        stderr = ''
        if self._process:
            stderr = self._process.readAllStandardError().data().decode(
                'utf-8', errors='ignore'
            ).strip()

        if stderr:
            logger.info("Print process stderr:\n%s", stderr)

        # Exit code 0 = success, 1 = user cancelled (normal), >1 = error
        if exit_code > 1:
            error_msg = f"Print process exited unexpectedly (code {exit_code})"
            if stderr:
                error_msg += f"\n{stderr}"
            self.error_occurred.emit(error_msg)

        # Cleanup always happens regardless of exit code
        self._cleanup()

    def _on_stderr_ready(self):
        """Forward subprocess stderr to parent stderr in real-time."""
        if self._process:
            data = self._process.readAllStandardError().data()
            if data:
                sys.stderr.buffer.write(data)
                sys.stderr.buffer.flush()

    def _on_process_error(self, error):
        """Handle process error.

        Args:
            error: QProcess.ProcessError
        """
        if self._process:
            error_msg = f"Print process error: {self._process.errorString()}"
            self.error_occurred.emit(error_msg)

        self._cleanup()

    def _on_timeout(self):
        """Handle operation timeout."""
        self.error_occurred.emit("Print operation timed out")
        self._cleanup()

    def _drain_socket(self):
        """Read any data already buffered in the socket and try to parse it.

        Called before cleanup destroys the socket so that a response that
        arrived between the last ``readyRead`` signal and now is not lost.
        """
        if self._socket is None:
            return

        try:
            # Give the OS a moment to deliver the last bytes.
            if self._socket.state() == QLocalSocket.LocalSocketState.ConnectedState:
                self._socket.waitForReadyRead(500)

            # Read everything sitting in the buffer.
            while self._socket.bytesAvailable() > 0:
                chunk = self._socket.readAll().data()
                if not chunk:
                    break
                if len(self._response_buffer) + len(chunk) > self.MAX_RESPONSE_BUFFER_SIZE:
                    break
                self._response_buffer.extend(chunk)

            # Try to parse whatever we have collected.
            if self._response_buffer:
                try:
                    response = json.loads(self._response_buffer.decode('utf-8'))
                    self._response_buffer.clear()
                    self._handle_response(response)
                except json.JSONDecodeError:
                    pass  # Incomplete — nothing we can do
        except (RuntimeError, OSError):
            pass  # Socket already gone

    def _cleanup(self):
        """Clean up resources.

        Safe to call multiple times - checks if resources exist before cleanup.
        """
        # Prevent re-entrant cleanup calls
        if self._is_cleaning_up:
            return
        self._is_cleaning_up = True

        # Stop timeout timer
        if self._timeout_timer is not None:
            try:
                self._timeout_timer.stop()
                self._timeout_timer.deleteLater()
            except RuntimeError:
                pass  # Already deleted
            finally:
                self._timeout_timer = None

        # Wait for process to finish first — this ensures the subprocess
        # has had a chance to write its response before we touch the socket.
        if self._process is not None:
            try:
                if self._process.state() == QProcess.ProcessState.Running:
                    if not self._process.waitForFinished(3000):
                        self._process.terminate()
                        if not self._process.waitForFinished(2000):
                            self._process.kill()
                            self._process.waitForFinished(1000)

                self._process.deleteLater()
            except RuntimeError:
                pass  # Already deleted
            finally:
                self._process = None

        # Drain any remaining data from the socket before destroying it.
        self._drain_socket()

        # Close socket
        if self._socket is not None:
            try:
                self._socket.disconnectFromServer()
                self._socket.deleteLater()
            except RuntimeError:
                pass  # Already deleted
            finally:
                self._socket = None

        # Stop server
        if self._server is not None:
            try:
                self._server.close()
                self._server.deleteLater()
            except RuntimeError:
                pass  # Already deleted
            finally:
                self._server = None

        # Delete temp PDF file
        if self._temp_pdf_path is not None:
            try:
                Path(self._temp_pdf_path).unlink(missing_ok=True)
            except Exception:
                pass
            finally:
                self._temp_pdf_path = None

        # Clear response buffer
        if hasattr(self, '_response_buffer'):
            self._response_buffer.clear()

        # Reset cleanup flag for next operation
        self._is_cleaning_up = False

    def is_running(self) -> bool:
        """Check if print process is currently running.

        Returns:
            True if process is active
        """
        return self._process is not None and self._process.state() == QProcess.ProcessState.Running

    def abort(self):
        """Abort ongoing print operation."""
        if self.is_running():
            self._cleanup()
            self.error_occurred.emit("Print operation aborted")
