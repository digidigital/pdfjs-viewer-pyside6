#!/usr/bin/env python3
"""Example: Disable stamp alt-text dialog to prevent crashes.

This example demonstrates how to disable the alt-text feature for stamp
annotations while keeping the delete functionality intact.

This is useful as a workaround for the Speicherzugriffsfehler crash that
occurs when using the alt-text dialog with Qt WebEngine.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel

from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig, PDFFeatures


class MainWindow(QMainWindow):
    """Main window demonstrating disabled alt-text feature."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Viewer - Stamp Alt-Text Disabled Example")
        self.resize(1200, 800)

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Instructions
        info_label = QLabel(
            "<b>Stamp Alt-Text Disabled Example</b><br>"
            "<br>"
            "This example disables the alt-text dialog for stamp annotations to prevent<br>"
            "Speicherzugriffsfehler crashes in Qt WebEngine.<br>"
            "<br>"
            "<b>Testing:</b><br>"
            "1. Click the stamp tool in the toolbar<br>"
            "2. Add a stamp image to the PDF<br>"
            "3. Right-click on the stamp<br>"
            "4. Notice: The 'Add or edit alt text' option is NOT visible<br>"
            "5. The delete button (bin icon) is still available<br>"
            "<br>"
            "<i>The alt-text feature is disabled by setting "
            "<code>stamp_alttext_enabled=False</code></i>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; border-radius: 5px;")
        layout.addWidget(info_label)

        # Create PDF viewer with stamp alt-text disabled
        features = PDFFeatures(
            stamp_enabled=True,  # Stamps are enabled
            stamp_alttext_enabled=False,  # But alt-text dialog is disabled
            load_enabled=True,  # Enable load button
        )

        config = PDFViewerConfig(features=features)
        self.pdf_viewer = PDFViewerWidget(config=config)
        layout.addWidget(self.pdf_viewer)

        # Status label
        self.status_label = QLabel("Ready. Load a PDF to begin.")
        layout.addWidget(self.status_label)

        # Connect signals
        self.pdf_viewer.pdf_loaded.connect(self._on_pdf_loaded)
        self.pdf_viewer.error_occurred.connect(
            lambda msg: print(f"Error: {msg}")
        )

        # Show blank page initially
        self.pdf_viewer.show_blank_page()

    def _on_pdf_loaded(self, metadata):
        """Handle PDF loaded event."""
        num_pages = metadata.get('numPages', 0)
        filename = metadata.get('filename', 'Untitled')
        self.status_label.setText(
            f"Loaded: {filename} ({num_pages} pages) - "
            f"Stamp alt-text feature is DISABLED"
        )


def main():
    """Run the example application."""
    app = QApplication(sys.argv)

    print("=" * 70)
    print("PDF Viewer - Stamp Alt-Text Disabled Example")
    print("=" * 70)
    print()
    print("This example demonstrates how to disable the alt-text dialog for")
    print("stamp annotations as a workaround for Qt WebEngine crashes.")
    print()
    print("Configuration used:")
    print("  features = PDFFeatures(")
    print("      stamp_enabled=True,")
    print("      stamp_alttext_enabled=False,  # Disables alt-text dialog")
    print("      load_enabled=True,")
    print("  )")
    print("=" * 70)
    print()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
