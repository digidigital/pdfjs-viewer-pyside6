"""JavaScript-Python bridge for PDF.js communication via QWebChannel."""

import base64
import json
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from .ui_translations import get_translations


class PDFJavaScriptBridge(QObject):
    """Bridge between PDF.js JavaScript and Python using QWebChannel.

    Handles bidirectional communication for save, print, load, and annotation events.
    All methods decorated with @pyqtSlot are callable from JavaScript.
    """

    # Signals emitted to Python
    save_requested = Signal(bytes, str)  # (pdf_data, filename)
    print_requested = Signal(bytes)  # (pdf_data)
    load_requested = Signal(str)  # (file_path)
    stamp_image_requested = Signal(str)  # (image_path)
    pdf_loaded = Signal(dict)  # (metadata)
    annotation_changed = Signal()
    page_changed = Signal(int, int)  # (current_page, total_pages)
    error_occurred = Signal(str)  # (error_message)
    text_copied = Signal(str)  # (copied_text)

    def __init__(self, parent: Optional[QObject] = None):
        """Initialize the bridge.

        Args:
            parent: Parent QObject (typically the PDFViewerWidget).
        """
        super().__init__(parent)
        self._parent_widget = parent
        self.tr = get_translations()  # Load UI translations

    @Slot(str, str)
    def save_pdf(self, data_base64: str, filename: str):
        """Called from JavaScript when save button is clicked.

        Args:
            data_base64: PDF data encoded as base64 string.
            filename: Suggested filename for save dialog.
        """
        try:
            # Decode base64 to bytes
            pdf_data = base64.b64decode(data_base64)

            # Emit signal first to avoid blocking JavaScript
            self.save_requested.emit(pdf_data, filename)

        except Exception as e:
            error_msg = f"Save error: {str(e)}"
            self.error_occurred.emit(error_msg)

    @Slot(str)
    def print_pdf(self, data_base64: str):
        """Called from JavaScript before printing.

        Args:
            data_base64: PDF data with annotations, encoded as base64.
        """
        try:
            pdf_data = base64.b64decode(data_base64)

            # Print dialog executes in separate process, no blocking needed
            # Process isolation prevents memory access errors (Speicherzugriffsfehler)
            self.print_requested.emit(pdf_data)
        except Exception as e:
            self.error_occurred.emit(f"Print error: {str(e)}")

    @Slot(result=str)
    def load_pdf_dialog(self) -> str:
        """Called from JavaScript when load button is clicked.

        Returns:
            Selected file path, or empty string if cancelled.
            JavaScript will call load_pdf_from_dialog to actually load the file.
        """
        try:
            if self._parent_widget:
                tr = get_translations()
                file_path, _ = QFileDialog.getOpenFileName(
                    self._parent_widget,
                    tr['open_pdf_title'],
                    "",
                    tr['pdf_files_filter']
                )

                # Return path to JavaScript
                # JavaScript will call load_pdf_from_dialog to load it
                return file_path if file_path else ""
            return ""
        except Exception as e:
            self.error_occurred.emit(f"Load dialog error: {str(e)}")
            return ""

    @Slot(str)
    def load_pdf_from_dialog(self, file_path: str):
        """Called from JavaScript to load a PDF file selected from dialog.

        Args:
            file_path: Path to PDF file to load.
        """
        try:
            if file_path and self._parent_widget:
                # Emit signal to backend to load the PDF
                # Backend will handle creating proper URLs and loading
                self.load_requested.emit(file_path)
        except Exception as e:
            self.error_occurred.emit(f"Load error: {str(e)}")

    @Slot(result=str)
    def load_stamp_dialog(self) -> str:
        """Called from JavaScript when stamp image load is clicked.

        Returns:
            Selected image file path, or empty string if cancelled.
            JavaScript will handle loading the returned path.
        """
        try:
            if self._parent_widget:
                tr = get_translations()
                file_path, _ = QFileDialog.getOpenFileName(
                    self._parent_widget,
                    tr['select_stamp_title'],
                    "",
                    tr['image_files_filter']
                )

                # Return path to JavaScript - don't emit signal
                # JavaScript will handle loading
                return file_path if file_path else ""
            return ""
        except Exception as e:
            self.error_occurred.emit(f"Stamp dialog error: {str(e)}")
            return ""

    @Slot(str)
    def notify_pdf_loaded(self, metadata_json: str):
        """Called from JavaScript when PDF loads successfully.

        Args:
            metadata_json: JSON string containing PDF metadata
                         (numPages, title, filename, etc.).
        """
        try:
            metadata = json.loads(metadata_json)
            self.pdf_loaded.emit(metadata)
        except Exception as e:
            self.error_occurred.emit(f"Metadata parse error: {str(e)}")

    @Slot()
    def notify_annotation_changed(self):
        """Called from JavaScript when annotations are modified."""
        self.annotation_changed.emit()

    @Slot(int, int)
    def notify_page_changed(self, current_page: int, total_pages: int):
        """Called from JavaScript when page changes.

        Args:
            current_page: Current page number (1-indexed).
            total_pages: Total number of pages.
        """
        self.page_changed.emit(current_page, total_pages)

    @Slot(str)
    def notify_error(self, error: str):
        """Called from JavaScript on errors.

        Args:
            error: Error message from JavaScript.
        """
        self.error_occurred.emit(error)

    @Slot(str, result=bool)
    def open_external_link(self, url: str) -> bool:
        """Called from JavaScript when external link is clicked.

        Args:
            url: The URL to open.

        Returns:
            True if link should be opened, False otherwise.
        """
        try:
            if self._parent_widget:
                tr = get_translations()
                reply = QMessageBox.question(
                    self._parent_widget,
                    tr['open_link_title'],
                    tr['open_link_message'].format(url=url),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                return reply == QMessageBox.StandardButton.Yes
            return False
        except Exception as e:
            self.error_occurred.emit(f"Link dialog error: {str(e)}")
            return False

    @Slot(result=str)
    def get_theme(self) -> str:
        """Called from JavaScript to get current theme.

        Returns:
            "light" or "dark"
        """
        if self._parent_widget and hasattr(self._parent_widget, '_current_theme'):
            return self._parent_widget._current_theme.value
        return "light"

    @Slot(str)
    def copyToClipboard(self, text: str):
        """Called from JavaScript to copy text to system clipboard.

        Args:
            text: Text to copy to clipboard.
        """
        try:
            from PySide6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(text)

            # Emit signal so the widget can show a notification
            self.text_copied.emit(text)

        except Exception as e:
            error_msg = self.tr['clipboard_error'].format(error=str(e))
            self.error_occurred.emit(error_msg)
