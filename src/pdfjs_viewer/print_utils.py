"""Print utilities for PDF.js Viewer Widget."""

import atexit
import io
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QRadioButton, QButtonGroup, QSpinBox, QPushButton, QGroupBox,
    QFileDialog, QWidget, QMessageBox, QLineEdit, QProgressBar
)
from PySide6.QtPrintSupport import QPrinterInfo

from .print_translations import get_translation


class CustomPrintDialog(QDialog):
    """Custom print dialog with printer selection, page range, and PDF export.

    Features:
    - Printer selection from available printers
    - "Print to PDF File" option
    - Page range selection (all or custom range)
    - Number of copies
    - Auto-detects default printer
    - Progress bar for rendering progress
    """

    # Signal emitted when user clicks Print button and settings are valid
    print_requested = Signal(dict)  # settings dictionary
    # Signal emitted when user requests cancellation during printing
    cancel_requested = Signal()

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
        self._print_in_progress: bool = False

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
        self.from_page_spin.setFixedWidth(70)  # Fixed width for ~5 digits
        self.from_page_spin.valueChanged.connect(self._on_from_page_changed)
        custom_range_layout.addWidget(self.from_page_spin)

        self.to_label = QLabel(self.tr['to'])
        custom_range_layout.addWidget(self.to_label)

        self.to_page_spin = QSpinBox()
        self.to_page_spin.setMinimum(1)
        self.to_page_spin.setMaximum(self.total_pages)
        self.to_page_spin.setValue(self.total_pages)
        self.to_page_spin.setEnabled(False)
        self.to_page_spin.setFixedWidth(70)  # Fixed width for ~5 digits
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

        # Progress bar (hidden initially, shown during rendering)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()  # Hidden until printing starts
        layout.addWidget(self.progress_bar)

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
        """Update 'To' page minimum when 'From' page changes."""
        self.to_page_spin.setMinimum(value)
        if self.to_page_spin.value() < value:
            self.to_page_spin.setValue(value)

    def _on_to_page_changed(self, value: int):
        """Update 'From' page maximum when 'To' page changes."""
        self.from_page_spin.setMaximum(value)
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

            # Mark that printing has started
            self._print_in_progress = True

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

            # Show progress bar
            self.progress_bar.setValue(0)
            self.progress_bar.show()

            # Disable buttons to prevent double-click
            self.print_btn.setEnabled(False)

            # Process events to show the status label and progress bar
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()

            # Emit signal with settings for external handling
            settings = self.get_settings()
            self.print_requested.emit(settings)

        except Exception as e:
            print(f"Error in print dialog: {e}")
            QMessageBox.critical(
                self,
                self.tr['error_title'],
                self.tr['error_msg'].format(error=str(e))
            )

    def get_settings(self) -> dict:
        """Get current print settings."""
        printer_info = self.get_printer_info()
        return {
            'accepted': True,
            'print_to_pdf': self.print_to_pdf_file,
            'printer_name': self.selected_printer,
            'page_range': self.page_range,
            'num_copies': self.num_copies,
            'output_path': self.output_path,
            'printer_available': printer_info is not None if not self.print_to_pdf_file else True
        }

    def is_print_in_progress(self) -> bool:
        """Check if printing is currently in progress."""
        return self._print_in_progress

    def _update_progress_ui(self, current: int, total: int):
        """Update the progress bar UI elements.

        Args:
            current: Current page being rendered (1-indexed)
            total: Total number of pages to render
        """
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)

        progress_text = self.tr.get(
            'rendering_page',
            'Rendering page {current} of {total}...'
        ).format(current=current, total=total)
        self.status_label.setText(progress_text)

    def finish_printing(self, success: bool = True):
        """Called when printing is complete to close the dialog.

        Args:
            success: Whether printing completed successfully
        """
        self._print_in_progress = False

        if success:
            self.accept()
        else:
            # Keep dialog open on failure so user can see error
            self.print_btn.setEnabled(True)
            self.progress_bar.hide()

    def reject(self):
        """Override reject to handle cancellation during printing."""
        if self._print_in_progress:
            self.cancel_requested.emit()
            self._print_in_progress = False

        super().reject()

    def get_printer_info(self) -> Optional[QPrinterInfo]:
        """Get QPrinterInfo for selected printer."""
        if self.print_to_pdf_file or not self.selected_printer:
            return None

        try:
            for printer_info in QPrinterInfo.availablePrinters():
                if printer_info.printerName() == self.selected_printer:
                    return printer_info
            return None
        except Exception as e:
            print(f"Error getting printer info: {e}")
            return None


class TempFileManager:
    """Manages temporary PDF files with automatic cleanup."""

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
        """Create temp file with original filename in managed directory."""
        self._ensure_initialized()

        safe_name = Path(original_name).name
        if not safe_name:
            safe_name = "document.pdf"

        temp_path = self.temp_dir / safe_name

        counter = 1
        while temp_path.exists():
            stem = Path(safe_name).stem
            suffix = Path(safe_name).suffix or ".pdf"
            temp_path = self.temp_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        try:
            temp_path.write_bytes(data)
            return temp_path
        except Exception as e:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise IOError(f"Failed to write temp PDF file: {e}") from e

    def cleanup(self):
        """Remove all temp files and directory."""
        if not self._initialized or not self.temp_dir:
            return

        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

        self._initialized = False
        self.temp_dir = None


# Global temp file manager instance
_temp_file_manager: Optional[TempFileManager] = None


def get_temp_file_manager() -> TempFileManager:
    """Get or create global temp file manager instance."""
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
        pdf_input = io.BytesIO(pdf_data)
        with pikepdf.open(pdf_input) as pdf:
            pdf_output = pikepdf.new()
            try:
                total_pages = len(pdf.pages)
                from_page = max(1, min(from_page, total_pages))
                to_page = max(from_page, min(to_page, total_pages))

                for page_num in range(from_page - 1, to_page):
                    pdf_output.pages.append(pdf.pages[page_num])

                pdf_output.save(output_path)
                return True
            finally:
                pdf_output.close()

    except Exception as e:
        print(f"Error exporting PDF pages: {e}")
        raise
