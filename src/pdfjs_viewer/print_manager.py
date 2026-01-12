"""Print process manager for isolated print dialog handling.

This module manages the lifecycle of the separate print process, including:
- Process spawning and shutdown
- IPC communication via QLocalSocket/QLocalServer
- Error recovery and timeout handling
- Resource cleanup
"""

import sys
import json
import base64
import uuid
from typing import Optional, Dict, Any
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QProcess, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket


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
        self._response_buffer = bytearray()
        self._is_cleaning_up = False  # Prevent multiple cleanup calls

    def show_print_dialog_and_print(
        self,
        pdf_data: bytes,
        total_pages: int,
        timeout_ms: int = 300000  # 5 minutes default
    ) -> None:
        """Show print dialog in separate process and execute print if accepted.

        This is a non-blocking operation. Results are emitted via signals:
        - print_completed(success, message) when done
        - error_occurred(error_msg) on error

        Args:
            pdf_data: PDF file bytes
            total_pages: Total number of pages
            timeout_ms: Timeout in milliseconds (default 5 minutes)
        """
        try:
            # Reset cleanup flag for new operation
            self._is_cleaning_up = False

            # Generate unique socket name
            self._socket_name = f"pdfjs_print_{uuid.uuid4().hex[:8]}"

            # Create IPC server
            self._server = QLocalServer(self)
            if not self._server.listen(self._socket_name):
                self.error_occurred.emit(f"Failed to create IPC server: {self._server.errorString()}")
                return

            # Wait for connection
            self._server.newConnection.connect(self._on_new_connection)

            # Find print_process.py module
            print_process_path = self._find_print_process_module()
            if not print_process_path:
                self.error_occurred.emit("Failed to find print_process.py module")
                self._cleanup()
                return

            # Start print process
            self._process = QProcess(self)
            self._process.finished.connect(self._on_process_finished)
            self._process.errorOccurred.connect(self._on_process_error)

            # Get command (PyInstaller compatible)
            executable, args = self._get_print_process_command()

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

            # Store PDF data for sending after connection
            self._pending_request = {
                'command': 'show_and_print',
                'total_pages': total_pages,
                'pdf_data': base64.b64encode(pdf_data).decode('ascii')
            }

        except Exception as e:
            self.error_occurred.emit(f"Failed to initialize print process: {str(e)}")
            self._cleanup()

    def _get_print_process_command(self) -> tuple:
        """Get command to run print process (PyInstaller compatible).

        Returns:
            (executable, args) tuple
        """
        # Detect if running in PyInstaller frozen app
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # PyInstaller frozen app
            # sys._MEIPASS points to the temporary folder where PyInstaller extracts files
            base_path = Path(sys._MEIPASS)

            # Find the print_process script
            # PyInstaller extracts to: sys._MEIPASS/pdfjs_viewer/print_process/__main__.py
            script_path = base_path / 'pdfjs_viewer' / 'print_process' / '__main__.py'

            if script_path.exists():
                # Run script directly with frozen Python interpreter
                return (sys.executable, [str(script_path), self._socket_name])
            else:
                # Fallback: try to run as module (might work in some PyInstaller configs)
                return (sys.executable, ['-m', 'pdfjs_viewer.print_process', self._socket_name])
        else:
            # Normal Python environment - use -m
            return (sys.executable, ['-m', 'pdfjs_viewer.print_process', self._socket_name])

    def _find_print_process_module(self) -> Optional[Path]:
        """Find the print_process.py module.

        Returns:
            Path to print_process.py or None if not found

        Note: This method is kept for backwards compatibility but is no longer used.
        Use _get_print_process_command() instead.
        """
        try:
            # Try to import the module to get its location
            import pdfjs_viewer.print_process
            module_file = pdfjs_viewer.print_process.__file__
            if module_file:
                return Path(module_file)
        except Exception:
            pass

        # Fallback: look relative to this file
        try:
            current_file = Path(__file__)
            print_process = current_file.parent / 'print_process.py'
            if print_process.exists():
                return print_process
        except Exception:
            pass

        return None

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

    def _on_ready_read(self):
        """Handle data received from print process."""
        if not self._socket:
            return

        try:
            # Read all available data
            self._response_buffer.extend(self._socket.readAll().data())

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
        # Only report error if process crashed (not normal exit 0 or 1)
        # Exit code 0 = success, 1 = user cancelled (normal), >1 = error
        if exit_code > 1:
            # Process crashed or failed unexpectedly
            if self._process:
                stderr = self._process.readAllStandardError().data().decode('utf-8', errors='ignore')
                error_msg = f"Print process exited unexpectedly (code {exit_code})"
                if stderr:
                    error_msg += f"\n{stderr}"
                self.error_occurred.emit(error_msg)

        # Cleanup always happens regardless of exit code
        self._cleanup()

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

        # Close socket - but give it time to read any pending data first
        if self._socket is not None:
            try:
                # Allow any pending reads to complete
                if self._socket.state() == QLocalSocket.LocalSocketState.ConnectedState:
                    self._socket.waitForReadyRead(200)  # Brief wait for final data
                self._socket.disconnectFromServer()
                self._socket.deleteLater()
            except RuntimeError:
                pass  # Already deleted
            finally:
                self._socket = None

        # Stop server - this closes all connections
        if self._server is not None:
            try:
                self._server.close()
                self._server.deleteLater()
            except RuntimeError:
                pass  # Already deleted
            finally:
                self._server = None

        # Wait for process to finish naturally (don't force terminate unless necessary)
        if self._process is not None:
            try:
                if self._process.state() == QProcess.ProcessState.Running:
                    # Give process time to finish naturally (it should exit on its own)
                    if not self._process.waitForFinished(3000):
                        # Only terminate if it didn't finish in time
                        self._process.terminate()
                        if not self._process.waitForFinished(2000):
                            self._process.kill()
                            self._process.waitForFinished(1000)

                self._process.deleteLater()
            except RuntimeError:
                pass  # Already deleted
            finally:
                self._process = None

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
