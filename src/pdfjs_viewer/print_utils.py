"""Print utilities for PDF.js Viewer Widget."""

import atexit
import io
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import QThread, Signal, QRunnable, QThreadPool, QObject, Qt, QTimer
from PySide6.QtGui import QImage, QPainter, QPageLayout
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QRadioButton, QButtonGroup, QSpinBox, QPushButton, QGroupBox,
    QFileDialog, QWidget, QMessageBox, QLineEdit
)

from .print_translations import get_translation


class CustomPrintDialog(QDialog):
    """Custom print dialog with printer selection, page range, and PDF export.

    Features:
    - Printer selection from available printers
    - "Print to PDF File" option
    - Page range selection (all or custom range)
    - Number of copies
    - Auto-detects default printer
    """

    def __init__(self, parent: Optional[QWidget] = None, total_pages: int = 1):
        """Initialize custom print dialog.

        Args:
            parent: Parent widget
            total_pages: Total number of pages in the PDF
        """
        super().__init__(parent)
        self.total_pages = total_pages
        self.selected_printer: Optional[str] = None
        self.print_to_pdf_file: bool = False
        self.page_range: Tuple[int, int] = (1, total_pages)
        self.num_copies: int = 1
        self.output_path: Optional[str] = None

        # Get translations for current system language
        self.tr = get_translation()

        # Store print to PDF string (translated)
        self.PRINT_TO_PDF = self.tr['print_to_pdf']

        self.setWindowTitle(self.tr['dialog_title'])
        self.setModal(True)
        self.setMinimumWidth(450)

        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Printer selection group
        printer_group = QGroupBox(self.tr['printer_group'])
        printer_layout = QVBoxLayout()

        self.printer_combo = QComboBox()
        self._populate_printers()
        self.printer_combo.currentIndexChanged.connect(self._on_printer_changed)
        printer_layout.addWidget(self.printer_combo)

        self.printer_info_label = QLabel()
        self.printer_info_label.setStyleSheet("color: gray; font-size: 10pt;")
        self.printer_info_label.setWordWrap(True)
        printer_layout.addWidget(self.printer_info_label)

        printer_group.setLayout(printer_layout)
        layout.addWidget(printer_group)

        # Page range group
        page_group = QGroupBox(self.tr['page_range_group'])
        page_layout = QVBoxLayout()

        self.page_button_group = QButtonGroup(self)

        self.all_pages_radio = QRadioButton(self.tr['all_pages'])
        self.all_pages_radio.setChecked(True)
        self.page_button_group.addButton(self.all_pages_radio)
        page_layout.addWidget(self.all_pages_radio)

        # Custom range layout
        custom_range_layout = QHBoxLayout()
        self.custom_range_radio = QRadioButton(self.tr['pages_from'])
        self.page_button_group.addButton(self.custom_range_radio)
        custom_range_layout.addWidget(self.custom_range_radio)

        self.from_page_spin = QSpinBox()
        self.from_page_spin.setMinimum(1)
        self.from_page_spin.setMaximum(self.total_pages)
        self.from_page_spin.setValue(1)
        self.from_page_spin.setEnabled(False)
        self.from_page_spin.valueChanged.connect(self._on_from_page_changed)
        custom_range_layout.addWidget(self.from_page_spin)

        self.to_label = QLabel(self.tr['to'])
        custom_range_layout.addWidget(self.to_label)

        self.to_page_spin = QSpinBox()
        self.to_page_spin.setMinimum(1)
        self.to_page_spin.setMaximum(self.total_pages)
        self.to_page_spin.setValue(self.total_pages)
        self.to_page_spin.setEnabled(False)
        self.to_page_spin.valueChanged.connect(self._on_to_page_changed)
        custom_range_layout.addWidget(self.to_page_spin)

        custom_range_layout.addStretch()
        page_layout.addLayout(custom_range_layout)

        # Connect radio buttons
        self.custom_range_radio.toggled.connect(self._on_range_toggled)

        page_group.setLayout(page_layout)
        layout.addWidget(page_group)

        # Copies group
        copies_group = QGroupBox(self.tr['copies_group'])
        copies_layout = QHBoxLayout()

        copies_layout.addWidget(QLabel(self.tr['num_copies']))
        self.copies_spin = QSpinBox()
        self.copies_spin.setMinimum(1)
        self.copies_spin.setMaximum(999)
        self.copies_spin.setValue(1)
        copies_layout.addWidget(self.copies_spin)
        copies_layout.addStretch()

        copies_group.setLayout(copies_layout)
        layout.addWidget(copies_group)

        # PDF output path group (only shown for Print to PDF)
        pdf_output_group = QGroupBox(self.tr['pdf_output_group'])
        pdf_output_layout = QHBoxLayout()

        pdf_output_layout.addWidget(QLabel(self.tr['save_to_label']))
        self.pdf_path_edit = QLineEdit()
        self.pdf_path_edit.setPlaceholderText("document.pdf")
        self.pdf_path_edit.setEnabled(False)
        pdf_output_layout.addWidget(self.pdf_path_edit, stretch=1)

        self.browse_btn = QPushButton("...")
        self.browse_btn.setMaximumWidth(40)
        self.browse_btn.setEnabled(False)
        self.browse_btn.clicked.connect(self._browse_output_path)
        pdf_output_layout.addWidget(self.browse_btn)

        pdf_output_group.setLayout(pdf_output_layout)
        layout.addWidget(pdf_output_group)

        # Status label (invisible placeholder reserves space, shown when printing starts)
        self.status_label = QLabel(" ")  # Invisible placeholder text
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: white;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
                min-height: 20px;
            }
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton(self.tr['cancel'])
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.print_btn = QPushButton(self.tr['print'])
        self.print_btn.setDefault(True)
        self.print_btn.clicked.connect(self._on_print_clicked)
        button_layout.addWidget(self.print_btn)

        layout.addLayout(button_layout)

        # Update printer info
        self._on_printer_changed(0)

    def _populate_printers(self):
        """Populate printer combo box with available printers."""
        try:
            # Get all available printers
            available_printers = QPrinterInfo.availablePrinters()
            default_printer = QPrinterInfo.defaultPrinter()

            # Check if there are any printers or a valid default
            has_printers = len(available_printers) > 0
            has_default = default_printer is not None and not default_printer.printerName().strip() == ""

            # Add "Print to PDF File" option
            if not has_printers or not has_default:
                # No printers available, make PDF first option
                self.printer_combo.addItem(self.PRINT_TO_PDF)

            # Add available printers
            default_index = 0
            for i, printer_info in enumerate(available_printers):
                printer_name = printer_info.printerName()
                if printer_name:
                    # Calculate index offset (0 if no PDF added yet, 1 if PDF is first)
                    offset = 0 if (has_printers and has_default) else 1
                    self.printer_combo.addItem(printer_name)

                    # Check if this is the default printer
                    if has_default and printer_info.printerName() == default_printer.printerName():
                        default_index = i + offset

            # Add "Print to PDF File" at the end if printers exist
            if has_printers and has_default:
                self.printer_combo.addItem(self.PRINT_TO_PDF)

            # Set default selection
            if has_default and has_printers:
                self.printer_combo.setCurrentIndex(default_index)
            else:
                # No default printer, select "Print to PDF File"
                self.printer_combo.setCurrentIndex(0)

        except Exception as e:
            # Error getting printers, fall back to PDF only
            print(f"Error enumerating printers: {e}")
            self.printer_combo.addItem(self.PRINT_TO_PDF)

    def _on_printer_changed(self, index: int):
        """Handle printer selection change."""
        try:
            printer_name = self.printer_combo.currentText()

            if printer_name == self.PRINT_TO_PDF:
                self.printer_info_label.setText(self.tr['type_pdf'])
                self.print_btn.setText(self.tr['print'])  # Always "Print", not "Save PDF..."
                self.print_to_pdf_file = True
                self.selected_printer = None
                # Enable PDF output path controls
                self.pdf_path_edit.setEnabled(True)
                self.browse_btn.setEnabled(True)
            else:
                # Get printer info - iterate through available printers to find match
                printer_info = None
                for available in QPrinterInfo.availablePrinters():
                    if available.printerName() == printer_name:
                        printer_info = available
                        break

                if printer_info is not None:
                    # Get printer type description
                    if printer_info.isDefault():
                        info_text = self.tr['type_default']
                    elif printer_info.isRemote():
                        info_text = self.tr['type_network']
                    else:
                        info_text = self.tr['type_local']

                    self.printer_info_label.setText(info_text)
                else:
                    self.printer_info_label.setText(self.tr['type_printer'])

                self.print_btn.setText(self.tr['print'])
                self.print_to_pdf_file = False
                self.selected_printer = printer_name
                # Disable PDF output path controls
                self.pdf_path_edit.setEnabled(False)
                self.browse_btn.setEnabled(False)

        except Exception as e:
            print(f"Error updating printer info: {e}")
            self.printer_info_label.setText("")

    def _browse_output_path(self):
        """Open file dialog to select PDF output path."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr['save_dialog_title'],
            self.pdf_path_edit.text() or "document.pdf",
            self.tr['pdf_files']
        )

        if file_path:
            self.pdf_path_edit.setText(file_path)

    def _on_range_toggled(self, checked: bool):
        """Handle page range radio button toggle."""
        self.from_page_spin.setEnabled(checked)
        self.to_page_spin.setEnabled(checked)

    def _on_from_page_changed(self, value: int):
        """Update 'To' page minimum when 'From' page changes.

        This ensures the user cannot select an invalid range where From > To.
        """
        # Update minimum of "To" spin box to match current "From" value
        self.to_page_spin.setMinimum(value)

        # If current "To" value is less than new "From" value, adjust it
        if self.to_page_spin.value() < value:
            self.to_page_spin.setValue(value)

    def _on_to_page_changed(self, value: int):
        """Update 'From' page maximum when 'To' page changes.

        This ensures the user cannot select an invalid range where From > To.
        """
        # Update maximum of "From" spin box to match current "To" value
        self.from_page_spin.setMaximum(value)

        # If current "From" value is greater than new "To" value, adjust it
        if self.from_page_spin.value() > value:
            self.from_page_spin.setValue(value)

    def _on_print_clicked(self):
        """Handle print button click."""
        try:
            # Get page range
            if self.all_pages_radio.isChecked():
                self.page_range = (1, self.total_pages)
            else:
                from_page = self.from_page_spin.value()
                to_page = self.to_page_spin.value()

                # No validation needed - UI prevents invalid ranges
                self.page_range = (from_page, to_page)

            # Get number of copies
            self.num_copies = self.copies_spin.value()

            # If printing to PDF, validate output path
            if self.print_to_pdf_file:
                output_path = self.pdf_path_edit.text().strip()
                if not output_path:
                    QMessageBox.warning(
                        self,
                        self.tr['error_title'],
                        self.tr['specify_output_path']
                    )
                    return

                self.output_path = output_path

            # Show status message at bottom of dialog
            self.status_label.setText(self.tr.get('print_sending', 'Sending data to printer...'))
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #2196F3;
                    color: white;
                    padding: 10px;
                    border-radius: 4px;
                    font-weight: bold;
                    min-height: 20px;
                }
            """)

            # Disable buttons to prevent double-click
            self.print_btn.setEnabled(False)

            # Process events to show the status label
            from PySide6.QtCore import QTimer
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()

            # Close dialog after 6 seconds
            QTimer.singleShot(6000, self.accept)

        except Exception as e:
            print(f"Error in print dialog: {e}")
            QMessageBox.critical(
                self,
                self.tr['error_title'],
                self.tr['error_msg'].format(error=str(e))
            )

    def get_printer_info(self) -> Optional[QPrinterInfo]:
        """Get QPrinterInfo for selected printer.

        Returns:
            QPrinterInfo object or None if printing to PDF
        """
        if self.print_to_pdf_file or not self.selected_printer:
            return None

        try:
            # Iterate through available printers to find match
            for printer_info in QPrinterInfo.availablePrinters():
                if printer_info.printerName() == self.selected_printer:
                    return printer_info
            return None
        except Exception as e:
            print(f"Error getting printer info: {e}")
            return None


class TempFileManager:
    """Manages temporary PDF files with automatic cleanup.

    Creates a unique temp directory per app instance and ensures cleanup
    on normal exit, crashes, or interruptions.
    """

    def __init__(self):
        """Initialize temp file manager with unique directory."""
        self.temp_dir: Optional[Path] = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of temp directory."""
        if not self._initialized:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="pdfjs_viewer_"))
            atexit.register(self.cleanup)
            self._initialized = True

    def create_temp_pdf(self, data: bytes, original_name: str) -> Path:
        """Create temp file with original filename in managed directory.

        Args:
            data: PDF file bytes
            original_name: Original filename (will be sanitized)

        Returns:
            Path to created temp file
        """
        self._ensure_initialized()

        # Sanitize filename (keep only name, remove path)
        safe_name = Path(original_name).name
        if not safe_name:
            safe_name = "document.pdf"

        temp_path = self.temp_dir / safe_name

        # Handle duplicates with counter
        counter = 1
        while temp_path.exists():
            stem = Path(safe_name).stem
            suffix = Path(safe_name).suffix or ".pdf"
            temp_path = self.temp_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        # Write file
        try:
            temp_path.write_bytes(data)
            return temp_path
        except Exception as e:
            # Clean up on write failure
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise IOError(f"Failed to write temp PDF file: {e}") from e

    def cleanup(self):
        """Remove all temp files and directory.

        Called automatically via atexit. Safe to call multiple times.
        """
        if not self._initialized or not self.temp_dir:
            return

        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass  # Silent cleanup failure

        self._initialized = False
        self.temp_dir = None


class PrintWorkerSignals(QObject):
    """Signals for PrintWorker thread."""
    progress = Signal(int, int)  # current_page, total_pages
    finished = Signal(bool)  # success
    error = Signal(str)  # error_message


class PageRenderTask(QRunnable):
    """Runnable task for rendering a single PDF page."""

    def __init__(self, pdf_bytes: bytes, page_num: int, dpi: int, signals: QObject):
        super().__init__()
        self.pdf_bytes = pdf_bytes
        self.page_num = page_num
        self.dpi = dpi
        self.signals = signals
        self.result: Optional[QImage] = None
        self.error: Optional[str] = None

    def run(self):
        """Render the page to QImage."""
        try:
            import pypdfium2 as pdfium

            # Open PDF from bytes
            pdf = pdfium.PdfDocument(self.pdf_bytes)

            # Get page
            page = pdf.get_page(self.page_num)

            # Render at specified DPI
            bitmap = page.render(scale=self.dpi / 72.0)
            pil_image = bitmap.to_pil()

            # Convert to QImage
            # PIL image is RGB, convert to QImage
            width, height = pil_image.size
            bytes_data = pil_image.tobytes("raw", "RGB")

            self.result = QImage(bytes_data, width, height, width * 3, QImage.Format.Format_RGB888).copy()

            page.close()
            pdf.close()

        except Exception as e:
            self.error = f"Page {self.page_num + 1}: {str(e)}"


class PrintWorker(QThread):
    """Worker thread for printing PDF with Qt print dialog.

    Renders pages using pypdfium2 and prints to QPrinter.
    Supports parallel page rendering for improved performance.
    """

    progress = Signal(int, int)  # current_page, total_pages
    finished = Signal(bool)  # success
    error = Signal(str)  # error_message

    def __init__(
        self,
        pdf_data: bytes,
        printer: QPrinter,
        dpi: int = 300,
        fit_to_page: bool = True,
        parallel_pages: int = 4,
        from_page: Optional[int] = None,
        to_page: Optional[int] = None,
    ):
        """Initialize print worker.

        Args:
            pdf_data: PDF file bytes
            printer: Configured QPrinter instance
            dpi: Rendering DPI (higher = better quality, slower)
            fit_to_page: Scale to fit page vs actual size
            parallel_pages: Number of pages to render in parallel
            from_page: First page to print (1-indexed), None for all
            to_page: Last page to print (1-indexed, inclusive), None for all
        """
        super().__init__()
        self.pdf_data = pdf_data
        self.printer = printer
        self.dpi = dpi
        self.fit_to_page = fit_to_page
        self.parallel_pages = max(1, parallel_pages)
        self.from_page = from_page
        self.to_page = to_page
        self._interrupted = False

    def run(self):
        """Execute print job."""
        try:
            # Check if pypdfium2 is available
            try:
                import pypdfium2 as pdfium
            except ImportError:
                self.error.emit(
                    "pypdfium2 is not installed. "
                    "Please install it: pip install pypdfium2"
                )
                self.finished.emit(False)
                return

            # Open PDF
            pdf = pdfium.PdfDocument(self.pdf_data)
            page_count = len(pdf)

            if page_count == 0:
                self.error.emit("PDF document is empty")
                self.finished.emit(False)
                return

            # Get print range (use custom range if provided, otherwise all pages)
            if self.from_page is not None and self.to_page is not None:
                # Custom range from dialog (1-indexed)
                from_page = max(0, self.from_page - 1)
                to_page = min(page_count - 1, self.to_page - 1)
            elif self.printer.printRange() == QPrinter.PrintRange.PageRange:
                # Range from printer settings (legacy)
                from_page = max(0, self.printer.fromPage() - 1)
                to_page = min(page_count - 1, self.printer.toPage() - 1)
            else:
                # All pages
                from_page = 0
                to_page = page_count - 1

            # Start painter
            painter = QPainter(self.printer)

            if not painter.isActive():
                self.error.emit("Failed to start printer")
                self.finished.emit(False)
                return

            # Print pages
            for page_idx in range(from_page, to_page + 1):
                if self._interrupted or self.isInterruptionRequested():
                    painter.end()
                    self.finished.emit(False)
                    return

                # Emit progress
                self.progress.emit(page_idx - from_page + 1, to_page - from_page + 1)

                try:
                    # Render page
                    page = pdf.get_page(page_idx)

                    # Get page dimensions
                    page_width, page_height = page.get_size()

                    # Determine orientation
                    if page_width > page_height:
                        self.printer.setPageOrientation(QPageLayout.Orientation.Landscape)
                    else:
                        self.printer.setPageOrientation(QPageLayout.Orientation.Portrait)

                    # Render page to bitmap
                    bitmap = page.render(scale=self.dpi / 72.0)
                    pil_image = bitmap.to_pil()

                    # Convert to QImage
                    width, height = pil_image.size
                    bytes_data = pil_image.tobytes("raw", "RGB")
                    q_image = QImage(bytes_data, width, height, width * 3, QImage.Format.Format_RGB888)

                    # Get printer page size
                    page_rect = self.printer.pageRect(QPrinter.Unit.DevicePixel)

                    if self.fit_to_page:
                        # Scale to fit
                        from PySide6.QtCore import Qt
                        scaled_image = q_image.scaled(
                            int(page_rect.width()),
                            int(page_rect.height()),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        painter.drawImage(0, 0, scaled_image)
                    else:
                        # Draw at actual size
                        painter.drawImage(0, 0, q_image)

                    page.close()

                    # New page if not last
                    if page_idx < to_page:
                        if not self.printer.newPage():
                            raise Exception("Failed to create new page")

                except Exception as e:
                    # Log error but continue with next page
                    self.error.emit(f"Error printing page {page_idx + 1}: {str(e)}")

            # Finish
            painter.end()
            pdf.close()

            self.finished.emit(True)

        except Exception as e:
            self.error.emit(f"Print job failed: {str(e)}")
            self.finished.emit(False)

    def stop(self):
        """Request thread interruption."""
        self._interrupted = True
        self.requestInterruption()


# Global temp file manager instance
_temp_file_manager: Optional[TempFileManager] = None


def get_temp_file_manager() -> TempFileManager:
    """Get or create global temp file manager instance.

    Returns:
        TempFileManager singleton instance
    """
    global _temp_file_manager
    if _temp_file_manager is None:
        _temp_file_manager = TempFileManager()
    return _temp_file_manager


def export_pdf_pages(pdf_data: bytes, output_path: str, from_page: int, to_page: int) -> bool:
    """Export specific pages from PDF to a new file using pikepdf.

    Args:
        pdf_data: Source PDF as bytes
        output_path: Destination file path
        from_page: First page to export (1-indexed)
        to_page: Last page to export (1-indexed, inclusive)

    Returns:
        True if successful, False otherwise

    Raises:
        ImportError: If pikepdf is not installed
        Exception: If PDF export fails
    """
    try:
        import pikepdf
    except ImportError:
        raise ImportError(
            "pikepdf is required for PDF export. "
            "Install it with: pip install 'pdfjs-viewer-pyside6[qt-print]'"
        )

    try:
        # Open PDF from bytes
        pdf_input = io.BytesIO(pdf_data)
        pdf = pikepdf.open(pdf_input)

        # Create output PDF
        pdf_output = pikepdf.new()

        # Validate page range
        total_pages = len(pdf.pages)
        from_page = max(1, min(from_page, total_pages))
        to_page = max(from_page, min(to_page, total_pages))

        # Copy selected pages (convert to 0-indexed)
        for page_num in range(from_page - 1, to_page):
            pdf_output.pages.append(pdf.pages[page_num])

        # Save output
        pdf_output.save(output_path)

        # Close PDFs
        pdf.close()
        pdf_output.close()

        return True

    except Exception as e:
        print(f"Error exporting PDF pages: {e}")
        raise
