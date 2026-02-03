"""Separate process for print dialog handling.

This module runs in a separate process to isolate the print dialog from the
main application's QWebEngine, preventing memory access violations (Speicherzugriffsfehler)
that can occur when showing modal dialogs while WebEngine is active.
"""

import sys
import json
import time
import traceback
from multiprocessing import freeze_support
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPageLayout
from PySide6.QtNetwork import QLocalSocket
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

from ..print_utils import (
    CustomPrintDialog,
    export_pdf_pages,
)


def show_print_dialog_and_execute(
    total_pages: int,
    pdf_data: bytes,
    print_config: dict = None
) -> tuple:
    """Show print dialog and execute print job with progress tracking.

    Args:
        total_pages: Total number of pages in PDF
        pdf_data: PDF data bytes for printing
        print_config: Optional print configuration with 'dpi' and 'fit_to_page'

    Returns:
        Tuple of (dialog_result: dict, print_result: dict or None)
    """
    dialog = CustomPrintDialog(parent=None, total_pages=total_pages)

    # Track results
    results = {
        'settings': None,
        'print_result': None,
        'cancelled': False
    }

    def on_print_requested(settings):
        """Handle print_requested signal - execute print job with progress."""
        results['settings'] = settings
        results['print_result'] = perform_print_job_with_dialog(
            pdf_data, settings, dialog, print_config
        )

    def on_rejected():
        """Handle dialog rejected (Cancel or close button)."""
        results['cancelled'] = True

    # Connect signals
    dialog.print_requested.connect(on_print_requested)
    dialog.rejected.connect(on_rejected)

    # Execute dialog - this blocks until dialog closes
    dialog.exec()

    if results['cancelled'] or results['settings'] is None:
        return {'accepted': False}, None

    return results['settings'], results['print_result']


def perform_print_job_with_dialog(
    pdf_data: bytes,
    settings: dict,
    dialog: CustomPrintDialog,
    print_config: dict = None
) -> dict:
    """Execute print job with progress updates to dialog.

    Uses sequential rendering: render one page, print it, release memory, repeat.
    This minimizes memory usage and keeps the UI responsive.

    Args:
        pdf_data: PDF file bytes
        settings: Print settings from dialog
        dialog: The print dialog to update with progress
        print_config: Optional print configuration with 'dpi' and 'fit_to_page'

    Returns:
        Dictionary with success status and any error message
    """
    # Use config values or defaults
    if print_config is None:
        print_config = {}
    dpi = print_config.get('dpi', 300)
    fit_to_page = print_config.get('fit_to_page', True)

    # Track state
    cancelled = {'value': False}
    start_time = time.time()
    MIN_DIALOG_DISPLAY_TIME = 3.0

    def on_cancel_requested():
        """Handle cancel request from dialog."""
        cancelled['value'] = True

    def close_dialog_with_min_time(success: bool):
        """Close dialog ensuring minimum display time has elapsed."""
        if cancelled['value']:
            return

        elapsed = time.time() - start_time
        remaining = MIN_DIALOG_DISPLAY_TIME - elapsed

        if remaining > 0:
            # Wait remaining time while processing events
            wait_end = time.time() + remaining
            while time.time() < wait_end:
                QApplication.processEvents()
                time.sleep(0.05)

        dialog.finish_printing(success)

    # Connect cancel signal
    dialog.cancel_requested.connect(on_cancel_requested)

    temp_pdf_path = None

    try:
        if settings['print_to_pdf']:
            # Export to PDF file - quick, no progress needed
            output_path = settings['output_path']
            from_page, to_page = settings['page_range']

            try:
                success = export_pdf_pages(pdf_data, output_path, from_page, to_page)
                if not cancelled['value']:
                    close_dialog_with_min_time(success)
                if success:
                    return {'success': True, 'message': f'PDF saved to {output_path}'}
                else:
                    return {'success': False, 'error': 'Failed to export PDF'}
            except ImportError as e:
                if not cancelled['value']:
                    close_dialog_with_min_time(False)
                return {'success': False, 'error': str(e)}
            except Exception as e:
                if not cancelled['value']:
                    close_dialog_with_min_time(False)
                return {'success': False, 'error': f'PDF export failed: {str(e)}'}

        else:
            # Print to physical printer with progress tracking
            printer_name = settings['printer_name']

            # Find printer
            printer_info = None
            for available in QPrinterInfo.availablePrinters():
                if available.printerName() == printer_name:
                    printer_info = available
                    break

            if not printer_info:
                if not cancelled['value']:
                    close_dialog_with_min_time(False)
                return {'success': False, 'error': f'Printer not found: {printer_name}'}

            # Configure printer
            printer = QPrinter(printer_info, QPrinter.PrinterMode.HighResolution)
            printer.setCopyCount(settings['num_copies'])

            # Get page range
            from_page, to_page = settings['page_range']
            total_pages_to_print = to_page - from_page + 1

            # Import pypdfium2 for rendering
            try:
                import pypdfium2 as pdfium
            except ImportError:
                if not cancelled['value']:
                    close_dialog_with_min_time(False)
                return {'success': False, 'error': 'pypdfium2 is required for printing'}

            # Load PDF document
            try:
                import io
                pdf = pdfium.PdfDocument(io.BytesIO(pdf_data))
            except Exception as e:
                if not cancelled['value']:
                    close_dialog_with_min_time(False)
                return {'success': False, 'error': f'Failed to load PDF: {str(e)}'}

            errors = []
            painter = None

            try:
                # Start painter
                painter = QPainter(printer)
                if not painter.isActive():
                    if not cancelled['value']:
                        close_dialog_with_min_time(False)
                    return {'success': False, 'error': 'Failed to start printer'}

                is_first_page = True

                # Sequential loop: render -> print -> release for each page
                for i, page_idx in enumerate(range(from_page - 1, to_page)):
                    if cancelled['value']:
                        break

                    try:
                        # Render this page
                        page = pdf.get_page(page_idx)

                        # Get page dimensions for orientation
                        page_width, page_height = page.get_size()
                        is_landscape = page_width > page_height

                        # Render to bitmap
                        bitmap = page.render(scale=dpi / 72.0)
                        pil_image = bitmap.to_pil()

                        # Convert to bytes
                        width, height = pil_image.size
                        image_bytes = pil_image.tobytes("raw", "RGB")

                        # Release pdfium resources for this page
                        page.close()
                        del bitmap
                        del pil_image

                        # Set orientation before newPage/first page draw
                        if is_landscape:
                            printer.setPageOrientation(QPageLayout.Orientation.Landscape)
                        else:
                            printer.setPageOrientation(QPageLayout.Orientation.Portrait)

                        # New page for all except the first
                        if not is_first_page:
                            if not printer.newPage():
                                raise Exception("Failed to create new page")

                        # Re-query page rect after orientation change so scaling
                        # uses the correct dimensions for landscape vs portrait
                        page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)

                        # Create QImage from bytes and print
                        q_image = QImage(
                            image_bytes, width, height, width * 3,
                            QImage.Format.Format_RGB888
                        )

                        if fit_to_page:
                            scaled_image = q_image.scaled(
                                int(page_rect.width()),
                                int(page_rect.height()),
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            )
                            painter.drawImage(0, 0, scaled_image)
                            del scaled_image
                        else:
                            painter.drawImage(0, 0, q_image)

                        # Release memory
                        del q_image
                        del image_bytes

                        is_first_page = False

                        # Update progress
                        dialog._update_progress_ui(i + 1, total_pages_to_print)

                        # Process Qt events to keep UI responsive
                        QApplication.processEvents()

                    except Exception as e:
                        errors.append(f'Error on page {page_idx + 1}: {str(e)}')

            finally:
                # Close PDF document
                try:
                    pdf.close()
                except Exception:
                    pass

                # Finish printing
                if painter is not None:
                    painter.end()

            # Handle cancellation
            if cancelled['value']:
                return {'success': False, 'error': 'Print cancelled by user'}

            # Check for errors
            if errors:
                if not cancelled['value']:
                    close_dialog_with_min_time(False)
                return {'success': False, 'error': '; '.join(errors[:5])}

            # Close dialog with success
            if not cancelled['value']:
                close_dialog_with_min_time(True)

            return {'success': True}

    except Exception as e:
        if not cancelled['value']:
            dialog.finish_printing(False)
        return {'success': False, 'error': f'Print job failed: {str(e)}'}

    finally:
        # Disconnect cancel signal to avoid issues
        try:
            dialog.cancel_requested.disconnect(on_cancel_requested)
        except RuntimeError:
            pass

        # Clean up temp PDF file
        if temp_pdf_path is not None:
            try:
                temp_pdf_path.unlink()
            except Exception:
                pass


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


def main():
    """Print process entry point."""
    if len(sys.argv) < 2:
        print("Usage: print_process.py <socket_name>", file=sys.stderr)
        sys.exit(1)

    socket_name = sys.argv[1]

    app = QApplication(sys.argv)

    socket = QLocalSocket()
    socket.connectToServer(socket_name)

    if not socket.waitForConnected(5000):
        print(f"Failed to connect to socket: {socket.errorString()}", file=sys.stderr)
        sys.exit(1)

    pdf_file = None  # Track temp file for cleanup

    try:
        request_buffer = bytearray()

        if not socket.waitForReadyRead(30000):
            print("Timeout waiting for request", file=sys.stderr)
            sys.exit(1)

        while True:
            chunk = socket.readAll().data()
            if chunk:
                request_buffer.extend(chunk)

            try:
                request = json.loads(request_buffer.decode('utf-8'))
                break
            except json.JSONDecodeError:
                if not socket.waitForReadyRead(5000):
                    print(f"Incomplete JSON after timeout: {request_buffer[:200]}", file=sys.stderr)
                    raise

        command = request.get('command')
        response = {}

        if command == 'show_dialog':
            total_pages = request.get('total_pages', 1)
            dialog_result = show_print_dialog(total_pages)
            response = {'status': 'ok', 'result': dialog_result}

        elif command == 'show_and_print':
            total_pages = request.get('total_pages', 1)
            pdf_file = request.get('pdf_file')
            print_config = request.get('print_config')

            if not pdf_file:
                response = {'status': 'error', 'error': 'Missing pdf_file'}
            else:
                pdf_data = Path(pdf_file).read_bytes()
                dialog_result, print_result = show_print_dialog_and_execute(
                    total_pages, pdf_data, print_config
                )
                response = {
                    'status': 'ok',
                    'dialog_result': dialog_result,
                    'print_result': print_result
                }

        else:
            response = {'status': 'error', 'error': f'Unknown command: {command}'}

        response_data = json.dumps(response).encode('utf-8')
        if socket.state() == QLocalSocket.LocalSocketState.ConnectedState:
            socket.write(response_data)
            socket.flush()
            socket.waitForBytesWritten(5000)

    except Exception as e:
        error_response = {
            'status': 'error',
            'error': str(e),
            'traceback': traceback.format_exc()
        }
        try:
            if socket.state() == QLocalSocket.LocalSocketState.ConnectedState:
                response_data = json.dumps(error_response).encode('utf-8')
                socket.write(response_data)
                socket.waitForBytesWritten(1000)
        except Exception:
            pass
        print(f"Error in print process: {e}", file=sys.stderr)
        traceback.print_exc()

    finally:
        if socket.state() != QLocalSocket.LocalSocketState.UnconnectedState:
            socket.disconnectFromServer()
        if socket.state() != QLocalSocket.LocalSocketState.UnconnectedState:
            socket.waitForDisconnected(1000)

        # Belt-and-suspenders: delete temp file even if parent didn't
        if pdf_file:
            try:
                Path(pdf_file).unlink(missing_ok=True)
            except Exception:
                pass


if __name__ == '__main__':
    freeze_support()
    main()
