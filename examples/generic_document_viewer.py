"""Generic document viewer demonstration.

This example shows how to use the PDFViewerWidget's underlying QWebEngineView
to display other document types beyond PDFs:
- HTML files
- XML files
- Plain text files
- Images (PNG, JPG, etc.)
- Markdown (as HTML)

This is useful when you want to reuse the same viewer widget for previewing
various document types in your application.
"""
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QUrl

from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig


class GenericDocumentViewerWindow(QMainWindow):
    """Window demonstrating generic document viewing."""

    DOCUMENT_TYPES = {
        "PDF": {
            "extensions": ["*.pdf"],
            "filter": "PDF Files (*.pdf)",
            "method": "load_pdf"
        },
        "HTML": {
            "extensions": ["*.html", "*.htm"],
            "filter": "HTML Files (*.html *.htm)",
            "method": "load_url"
        },
        "XML": {
            "extensions": ["*.xml"],
            "filter": "XML Files (*.xml)",
            "method": "load_url"
        },
        "Text": {
            "extensions": ["*.txt", "*.md", "*.log"],
            "filter": "Text Files (*.txt *.md *.log)",
            "method": "load_url"
        },
        "Image": {
            "extensions": ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.svg"],
            "filter": "Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.svg)",
            "method": "load_url"
        },
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Generic Document Viewer Demo")
        self.resize(1200, 800)

        # Create main widget
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)

        # Info label
        info_label = QLabel(
            "<b>Generic Document Viewer</b><br>"
            "This example reuses the PDF viewer's QWebEngineView to display various document types."
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("padding: 10px;")
        main_layout.addWidget(info_label)

        # Control panel
        control_layout = QHBoxLayout()

        control_layout.addWidget(QLabel("Document Type:"))

        self.type_combo = QComboBox()
        self.type_combo.addItems(self.DOCUMENT_TYPES.keys())
        control_layout.addWidget(self.type_combo)

        load_btn = QPushButton("📁 Load Document")
        load_btn.clicked.connect(self._load_document)
        control_layout.addWidget(load_btn)

        load_sample_btn = QPushButton("📄 Load (HTML-Wrapped) Sample")
        load_sample_btn.clicked.connect(self._load_sample)
        control_layout.addWidget(load_sample_btn)

        control_layout.addStretch()

        main_layout.addLayout(control_layout)

        # Create viewer
        config = PDFViewerConfig()
        config.features.load_enabled = True
        self.viewer = PDFViewerWidget(config=config)
        main_layout.addWidget(self.viewer, stretch=1)

        # Connect signals
        self.viewer.pdf_loaded.connect(
            lambda meta: self.statusBar().showMessage(
                f"PDF loaded: {meta.get('filename', 'Unknown')} ({meta.get('numPages', 0)} pages)"
            )
        )
        self.viewer.error_occurred.connect(
            lambda msg: print(f"Error: {msg}")
        )

        # Show blank page initially
        self.viewer.show_blank_page()

        self.setCentralWidget(main_widget)

    def _load_document(self):
        """Load a document based on selected type."""
        doc_type = self.type_combo.currentText()
        type_info = self.DOCUMENT_TYPES[doc_type]

        # Build filter string
        filter_str = f"{type_info['filter']};;All Files (*)"

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Open {doc_type} File",
            str(Path.home()),
            filter_str
        )

        if file_path:
            try:
                self._load_file(file_path, doc_type)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Load Error",
                    f"Failed to load {doc_type}:\n{e}"
                )

    def _load_file(self, file_path: str, doc_type: str):
        """Load a file into the viewer.

        Args:
            file_path: Path to the file
            doc_type: Document type from DOCUMENT_TYPES
        """
        type_info = self.DOCUMENT_TYPES[doc_type]
        method = type_info["method"]

        if method == "load_pdf":
            # Use PDF.js for PDF files
            self.viewer.load_pdf(file_path)
            self.statusBar().showMessage(f"Loaded PDF: {Path(file_path).name}")

        elif method == "load_url":
            # Use QWebEngineView directly for other file types
            # Access the underlying web view
            web_view = self.viewer.backend.web_view

            if web_view:
                url = QUrl.fromLocalFile(str(Path(file_path).absolute()))
                web_view.setUrl(url)
                self.statusBar().showMessage(f"Loaded {doc_type}: {Path(file_path).name}")
            else:
                raise RuntimeError("Web view not initialized")

    def _load_sample(self):
        """Load a sample document based on type."""
        doc_type = self.type_combo.currentText()

        if doc_type == "HTML":
            self._load_sample_html()
        elif doc_type == "XML":
            self._load_sample_xml()
        elif doc_type == "Text":
            self._load_sample_text()
        else:
            QMessageBox.information(
                self,
                "Sample",
                f"No built-in sample for {doc_type}.\n"
                f"Please use 'Load Document' to load your own file."
            )

    def _load_sample_html(self):
        """Load a sample HTML document."""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Sample HTML Document</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 { color: #2196F3; }
        .feature {
            background: white;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body>
    <h1>Generic Document Viewer Demo</h1>
    <p>This HTML document is displayed using the same QWebEngineView that powers the PDF viewer.</p>

    <div class="feature">
        <h2>Features</h2>
        <ul>
            <li>Full HTML rendering with CSS</li>
            <li>JavaScript execution (if enabled)</li>
            <li>Responsive layout</li>
            <li>Image embedding</li>
        </ul>
    </div>

    <div class="feature">
        <h2>Use Cases</h2>
        <ul>
            <li>Preview HTML files in your application</li>
            <li>Display formatted documentation</li>
            <li>Show rich content alongside PDFs</li>
            <li>Reuse the same viewer component</li>
        </ul>
    </div>
</body>
</html>
"""
        web_view = self.viewer.backend.web_view
        if web_view:
            web_view.setHtml(html_content, QUrl("file:///"))
            self.statusBar().showMessage("Loaded sample HTML")

    def _load_sample_xml(self):
        """Load a sample XML document."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<document>
    <metadata>
        <title>Sample XML Document</title>
        <author>Generic Document Viewer</author>
        <date>2026-01-09</date>
    </metadata>
    <content>
        <section id="1">
            <heading>Introduction</heading>
            <paragraph>This is a sample XML document displayed in the viewer.</paragraph>
        </section>
        <section id="2">
            <heading>Features</heading>
            <items>
                <item>Syntax highlighting (browser default)</item>
                <item>Tree structure visualization</item>
                <item>Direct XML rendering</item>
            </items>
        </section>
    </content>
</document>"""

        # Create temporary HTML wrapper for better XML display
        html_wrapper = f"""
<!DOCTYPE html>
<html>
<head>
    <title>XML Viewer</title>
    <style>
        body {{
            font-family: 'Courier New', monospace;
            padding: 20px;
            background: #f5f5f5;
        }}
        pre {{
            background: white;
            padding: 20px;
            border-radius: 5px;
            overflow-x: auto;
        }}
    </style>
</head>
<body>
    <h2>XML Document</h2>
    <pre>{html_escape(xml_content)}</pre>
</body>
</html>
"""
        web_view = self.viewer.backend.web_view
        if web_view:
            web_view.setHtml(html_wrapper, QUrl("file:///"))
            self.statusBar().showMessage("Loaded sample XML")

    def _load_sample_text(self):
        """Load a sample text document."""
        text_content = """Generic Document Viewer Demo
=============================

This is a plain text file displayed in the viewer.

Features:
---------
• Plain text rendering
• Monospace font
• Preserves formatting
• Line breaks maintained

Use Cases:
----------
1. Log file viewing
2. Configuration file preview
3. Markdown source viewing
4. Code snippet display

Technical Details:
------------------
The viewer uses QWebEngineView which natively supports:
- HTML/CSS rendering
- Image formats (PNG, JPG, GIF, SVG, BMP)
- Plain text display
- XML visualization

This makes it perfect for multi-format document preview!
"""

        html_wrapper = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Text Viewer</title>
    <style>
        body {{
            font-family: 'Courier New', monospace;
            padding: 20px;
            background: #f5f5f5;
            max-width: 900px;
            margin: 0 auto;
        }}
        pre {{
            background: white;
            padding: 20px;
            border-radius: 5px;
            white-space: pre-wrap;
            line-height: 1.5;
        }}
    </style>
</head>
<body>
    <pre>{html_escape(text_content)}</pre>
</body>
</html>
"""
        web_view = self.viewer.backend.web_view
        if web_view:
            web_view.setHtml(html_wrapper, QUrl("file:///"))
            self.statusBar().showMessage("Loaded sample text")


def html_escape(text: str) -> str:
    """Escape HTML special characters."""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#x27;'))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = GenericDocumentViewerWindow()
    window.show()

    # Show info dialog
    QMessageBox.information(
        window,
        "Generic Document Viewer",
        "<h3>Multi-Format Document Viewer</h3>"
        "<p>This example demonstrates reusing the PDF viewer's QWebEngineView "
        "to display various document types:</p>"
        "<ul>"
        "<li><b>PDF:</b> Uses PDF.js (full annotation support)</li>"
        "<li><b>HTML:</b> Native browser rendering</li>"
        "<li><b>XML:</b> Formatted display</li>"
        "<li><b>Text:</b> Monospace formatting</li>"
        "<li><b>Images:</b> Native image rendering</li>"
        "</ul>"
        "<br>"
        "<p><b>How to use:</b></p>"
        "<ol>"
        "<li>Select document type from dropdown</li>"
        "<li>Click 'Load Document' to open your file</li>"
        "<li>Or click 'Load Sample' for built-in examples</li>"
        "</ol>"
        "<br>"
        "<p><i>Note: The same QWebEngineView instance handles all formats, "
        "making it efficient for multi-format document preview applications.</i></p>"
    )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
