"""Separate process for print dialog handling.

This module runs in a separate process to isolate the print dialog from the
main application's QWebEngine, preventing memory access violations (Speicherzugriffsfehler)
that can occur when showing modal dialogs while WebEngine is active.
"""

import sys
import json
import base64
import traceback
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer, QEventLoop, QThread
from PySide6.QtNetwork import QLocalSocket
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

from ..print_utils import CustomPrintDialog, PrintWorker, export_pdf_pages


def show_print_dialog(total_pages: int) -> Optional[dict]:
    """Show print dialog and return user selections.

    Args:
        total_pages: Total number of pages in PDF

    Returns:
        Dictionary with print settings or None if cancelled
    """
    dialog = CustomPrintDialog(parent=None, total_pages=total_pages)
    result = dialog.exec()

    if result:
        # Get printer info
        printer_info = dialog.get_printer_info()

        return {
            'accepted': True,
            'print_to_pdf': dialog.print_to_pdf_file,
            'printer_name': dialog.selected_printer,
            'page_range': dialog.page_range,
            'num_copies': dialog.num_copies,
            'output_path': dialog.output_path,
            'printer_available': printer_info is not None if not dialog.print_to_pdf_file else True
        }
    else:
        return {'accepted': False}


def perform_print_job(pdf_data: bytes, settings: dict) -> dict:
    """Execute print job with given settings.

    Args:
        pdf_data: PDF file bytes
        settings: Print settings from dialog

    Returns:
        Dictionary with success status and any error message
    """
    try:
        if settings['print_to_pdf']:
            # Export to PDF file
            output_path = settings['output_path']
            from_page, to_page = settings['page_range']

            try:
                success = export_pdf_pages(pdf_data, output_path, from_page, to_page)
                if success:
                    return {'success': True, 'message': f'PDF saved to {output_path}'}
                else:
                    return {'success': False, 'error': 'Failed to export PDF'}
            except ImportError as e:
                return {'success': False, 'error': str(e)}
            except Exception as e:
                return {'success': False, 'error': f'PDF export failed: {str(e)}'}

        else:
            # Print to physical printer
            printer_name = settings['printer_name']

            # Find printer
            printer_info = None
            for available in QPrinterInfo.availablePrinters():
                if available.printerName() == printer_name:
                    printer_info = available
                    break

            if not printer_info:
                return {'success': False, 'error': f'Printer not found: {printer_name}'}

            # Note: We rely on the timeout mechanism below to detect offline/unavailable printers
            # Direct printer state checking is not consistently available across Qt versions

            # Configure printer
            printer = QPrinter(printer_info, QPrinter.PrinterMode.HighResolution)
            printer.setCopyCount(settings['num_copies'])

            # Create print worker
            from_page, to_page = settings['page_range']
            worker = PrintWorker(
                pdf_data=pdf_data,
                printer=printer,
                dpi=300,
                fit_to_page=True,
                from_page=from_page,
                to_page=to_page
            )

            # Track print result
            result = {'success': False, 'error': None}
            errors = []

            def on_finished(success):
                result['success'] = success
                if not success and not result['error']:
                    result['error'] = 'Print job failed'

            def on_error(error_msg):
                errors.append(error_msg)
                result['error'] = '; '.join(errors)

            worker.finished.connect(on_finished)
            worker.error.connect(on_error)

            # Start worker and wait for completion with timeout
            worker.start()

            # Process events while waiting for worker to complete
            # This ensures signals are delivered properly
            # Maximum wait time: 5 minutes (300 seconds)
            max_wait_time = 300000  # milliseconds
            elapsed_time = 0
            wait_interval = 100  # milliseconds

            while worker.isRunning() and elapsed_time < max_wait_time:
                QApplication.processEvents()
                worker.wait(wait_interval)
                elapsed_time += wait_interval

            # Check if timeout occurred
            if worker.isRunning():
                worker.stop()  # Request worker to stop
                worker.wait(5000)  # Wait up to 5 seconds for clean shutdown
                if worker.isRunning():
                    worker.terminate()  # Force terminate if still running
                return {'success': False, 'error': 'Print job timeout - printer may be offline or unresponsive'}

            # Process any remaining events after thread finishes
            QApplication.processEvents()

            return result

    except Exception as e:
        return {'success': False, 'error': f'Print job failed: {str(e)}'}


def main():
    """Print process entry point.

    Protocol:
    1. Connect to IPC socket (name passed as argv[1])
    2. Receive request: {'command': 'show_dialog'/'print', 'data': ...}
    3. Execute command
    4. Send response back
    5. Exit
    """
    if len(sys.argv) < 2:
        print("Usage: print_process.py <socket_name>", file=sys.stderr)
        sys.exit(1)

    socket_name = sys.argv[1]

    app = QApplication(sys.argv)

    # Connect to main process
    socket = QLocalSocket()
    socket.connectToServer(socket_name)

    if not socket.waitForConnected(5000):
        print(f"Failed to connect to socket: {socket.errorString()}", file=sys.stderr)
        sys.exit(1)

    try:
        # Read request - may come in multiple chunks for large PDFs
        request_buffer = bytearray()

        # Read first chunk
        if not socket.waitForReadyRead(30000):  # 30 second timeout
            print("Timeout waiting for request", file=sys.stderr)
            sys.exit(1)

        # Keep reading until we have complete JSON
        while True:
            chunk = socket.readAll().data()
            if chunk:
                request_buffer.extend(chunk)

            # Try to parse JSON
            try:
                request = json.loads(request_buffer.decode('utf-8'))
                break  # Success - complete JSON received
            except json.JSONDecodeError:
                # Incomplete JSON, wait for more data
                if not socket.waitForReadyRead(5000):
                    # No more data coming, this is an error
                    print(f"Incomplete JSON after timeout: {request_buffer[:200]}", file=sys.stderr)
                    raise

        command = request.get('command')
        response = {}

        if command == 'show_dialog':
            # Show print dialog
            total_pages = request.get('total_pages', 1)
            dialog_result = show_print_dialog(total_pages)
            response = {'status': 'ok', 'result': dialog_result}

        elif command == 'print':
            # Perform print job
            pdf_data_b64 = request.get('pdf_data')
            settings = request.get('settings')

            if not pdf_data_b64 or not settings:
                response = {'status': 'error', 'error': 'Missing pdf_data or settings'}
            else:
                pdf_data = base64.b64decode(pdf_data_b64)
                print_result = perform_print_job(pdf_data, settings)
                response = {'status': 'ok', 'result': print_result}

        elif command == 'show_and_print':
            # Combined: show dialog and print if accepted
            total_pages = request.get('total_pages', 1)
            pdf_data_b64 = request.get('pdf_data')

            if not pdf_data_b64:
                response = {'status': 'error', 'error': 'Missing pdf_data'}
            else:
                # Show dialog
                dialog_result = show_print_dialog(total_pages)

                if dialog_result and dialog_result.get('accepted'):
                    # User accepted, perform print (status shown in dialog)
                    pdf_data = base64.b64decode(pdf_data_b64)
                    print_result = perform_print_job(pdf_data, dialog_result)
                    response = {
                        'status': 'ok',
                        'dialog_result': dialog_result,
                        'print_result': print_result
                    }
                else:
                    # User cancelled
                    response = {
                        'status': 'ok',
                        'dialog_result': dialog_result,
                        'print_result': None
                    }

        else:
            response = {'status': 'error', 'error': f'Unknown command: {command}'}

        # Send response
        response_data = json.dumps(response).encode('utf-8')
        socket.write(response_data)
        socket.flush()

        # Wait for data to be written
        if not socket.waitForBytesWritten(5000):
            print(f"Warning: Failed to write response: {socket.errorString()}", file=sys.stderr)

    except Exception as e:
        # Send error response
        error_response = {
            'status': 'error',
            'error': str(e),
            'traceback': traceback.format_exc()
        }
        response_data = json.dumps(error_response).encode('utf-8')
        socket.write(response_data)
        socket.waitForBytesWritten(1000)
        print(f"Error in print process: {e}", file=sys.stderr)
        traceback.print_exc()

    finally:
        # Give parent process time to read response before disconnecting
        QThread.msleep(100)

        # Clean disconnect - only if still connected
        if socket.state() != QLocalSocket.LocalSocketState.UnconnectedState:
            socket.disconnectFromServer()
            socket.waitForDisconnected(1000)

    # Exit code 0 = success (including user cancellation)
    sys.exit(0)


if __name__ == '__main__':
    main()
