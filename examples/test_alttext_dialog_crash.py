#!/usr/bin/env python3
"""Test script to reproduce PDF.js alt-text dialog crash with unaltered PDF.js.

This script loads the vanilla PDF.js viewer directly to check if the alt-text
dialog crash occurs with unmodified PDF.js in QWebEngineView.

Usage:
    python test_alttext_dialog_crash.py [path/to/pdf/file]

Instructions:
    1. Load a PDF file
    2. Click on the stamp tool in the toolbar
    3. Add a stamp image to the PDF
    4. Right-click on the stamp and select "Add or edit alt text"
    5. In the alt-text dialog, either:
       - Enter some text and click Save, OR
       - Check "Mark as decorative" and click Save, OR
       - Click Cancel
    6. Check if the application crashes with Speicherzugriffsfehler
"""

import sys
from pathlib import Path

# Try to import PySide6 first, fall back to PyQt6
try:
    from PySide6.QtCore import QUrl
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QFileDialog, QLabel
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6 import __version__ as qt_version
    from PySide6.QtCore import qVersion
    QT_BINDING = "PySide6"
except ImportError:
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QFileDialog, QLabel
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage
    from PyQt6 import QtCore
    qt_version = QtCore.PYQT_VERSION_STR
    qVersion = QtCore.qVersion
    QT_BINDING = "PyQt6"


class TestWebEnginePage(QWebEnginePage):
    """Custom page to log JavaScript console messages."""

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        """Log JavaScript console messages."""
        level_str = {
            QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel: "INFO",
            QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel: "WARNING",
            QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel: "ERROR",
        }.get(level, "LOG")

        print(f"[JS {level_str}] {source_id}:{line_number} - {message}")


class PDFJSTestWindow(QMainWindow):
    """Main window for testing PDF.js alt-text dialog crash."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF.js Alt-Text Dialog Crash Test")
        self.resize(1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Instructions label
        instructions = QLabel(
            "<b>Instructions:</b><br>"
            "1. Load a PDF file<br>"
            "2. Click stamp tool, add a stamp image<br>"
            "3. Right-click stamp → 'Add or edit alt text'<br>"
            "4. Click Save or Cancel<br>"
            "5. Check if application crashes with Speicherzugriffsfehler"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Load PDF button
        load_btn = QPushButton("Load PDF File")
        load_btn.clicked.connect(self.load_pdf)
        layout.addWidget(load_btn)

        # Create web view with custom page
        self.web_view = QWebEngineView()
        custom_page = TestWebEnginePage(self.web_view)
        self.web_view.setPage(custom_page)
        layout.addWidget(self.web_view)

        # Status label
        self.status_label = QLabel("Ready. Load a PDF file to begin testing.")
        layout.addWidget(self.status_label)

        # Find PDF.js viewer path
        self.pdfjs_path = self._find_pdfjs_viewer()

        if self.pdfjs_path:
            self.status_label.setText(f"PDF.js found at: {self.pdfjs_path}")
        else:
            self.status_label.setText(
                "ERROR: PDF.js viewer.html not found!\n"
                "Please ensure PDF.js is installed in one of:\n"
                "- ../src/pdfjs_viewer/pdfjs/web/viewer.html\n"
                "- ../../pdfjs-viewer-pyside6/src/pdfjs_viewer/pdfjs/web/viewer.html\n"
                "- ../../pdfjs-viewer-pyqt6/src/pdfjs_viewer/pdfjs/web/viewer.html"
            )

    def _find_pdfjs_viewer(self) -> Path:
        """Find PDF.js viewer.html path."""
        # Check common locations relative to script location
        script_dir = Path(__file__).parent

        possible_paths = [
            # Relative to examples directory
            script_dir.parent / "src/pdfjs_viewer/pdfjs/web/viewer.html",

            # Sibling packages
            script_dir.parent.parent / "pdfjs-viewer-pyside6/src/pdfjs_viewer/pdfjs/web/viewer.html",
            script_dir.parent.parent / "pdfjs-viewer-pyqt6/src/pdfjs_viewer/pdfjs/web/viewer.html",

            # Absolute paths based on typical directory structure
            Path("/home/bjoern/Dokumente/python_progs/PDF_viewer_modules/pdfjs-viewer-pyside6/src/pdfjs_viewer/pdfjs/web/viewer.html"),
            Path("/home/bjoern/Dokumente/python_progs/PDF_viewer_modules/pdfjs-viewer-pyqt6/src/pdfjs_viewer/pdfjs/web/viewer.html"),
        ]

        for path in possible_paths:
            if path.exists():
                return path

        return None

    def load_pdf(self):
        """Open file dialog and load PDF in viewer."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF File",
            str(Path.home()),
            "PDF Files (*.pdf);;All Files (*)"
        )

        if not file_path:
            return

        if not self.pdfjs_path:
            self.status_label.setText("ERROR: Cannot load PDF - PDF.js viewer not found!")
            return

        # Convert to file:// URL
        pdf_url = QUrl.fromLocalFile(file_path).toString()

        # Load PDF.js viewer with the PDF file as parameter
        viewer_url = QUrl.fromLocalFile(str(self.pdfjs_path))
        # Add PDF file as query parameter: viewer.html?file=<pdf_path>
        viewer_url.setQuery(f"file={pdf_url}")

        print(f"\nLoading PDF.js viewer: {viewer_url.toString()}")
        print(f"PDF file: {pdf_url}")
        print("\nWaiting for PDF to load...")
        print("Follow the instructions to test the alt-text dialog crash.\n")

        self.web_view.setUrl(viewer_url)
        self.status_label.setText(f"Loaded: {Path(file_path).name}")


def main():
    """Run the test application."""
    app = QApplication(sys.argv)

    print("=" * 60)
    print("PDF.js Alt-Text Dialog Crash Test")
    print("=" * 60)
    print(f"Qt Binding: {QT_BINDING}")
    print(f"{QT_BINDING} version: {qt_version}")
    print(f"Qt version: {qVersion()}")
    print("=" * 60)
    print()

    # Load PDF from command line if provided
    window = PDFJSTestWindow()
    window.show()

    # Auto-load PDF if provided as argument
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        if Path(pdf_path).exists():
            print(f"Auto-loading PDF: {pdf_path}")
            window.status_label.setText(f"Auto-loading: {pdf_path}")

            pdf_url = QUrl.fromLocalFile(pdf_path).toString()
            viewer_url = QUrl.fromLocalFile(str(window.pdfjs_path))
            viewer_url.setQuery(f"file={pdf_url}")
            window.web_view.setUrl(viewer_url)
        else:
            print(f"ERROR: PDF file not found: {pdf_path}")

    sys.exit(app.exec() if QT_BINDING == "PyQt6" else app.exec())


if __name__ == "__main__":
    main()
