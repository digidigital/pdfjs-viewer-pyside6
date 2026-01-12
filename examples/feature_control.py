"""Feature control example.

Demonstrates how to disable specific UI features in the PDF viewer.
"""

import sys

from PySide6.QtWidgets import QApplication, QMainWindow
from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig, PDFFeatures, PDFSecurityConfig


def main():
    app = QApplication(sys.argv)

    # Configure features - disable some UI elements
    features = PDFFeatures(
        print_enabled=False,         # Disable printing
        save_enabled=True,           # Allow saving
        load_enabled=True,           # Enable file loading button
        presentation_mode=False,     # Disable presentation mode
        stamp_enabled=False,         # Disable stamp annotations
    )

    # Configure security
    security = PDFSecurityConfig(
        allow_external_links=False,  # Block external links
        block_remote_content=True,   # Block remote images/fonts
    )

    # Create configuration
    config = PDFViewerConfig(
        features=features,
        security=security,
    )

    # Create main window
    window = QMainWindow()
    window.setWindowTitle("PDF Viewer - Feature Control Example")
    window.resize(1024, 768)

    # Create PDF viewer with configuration
    viewer = PDFViewerWidget(config=config)

    # Connect signals
    viewer.pdf_loaded.connect(
        lambda meta: print(f"PDF loaded: {meta.get('filename', 'Unknown')}")
    )

    viewer.external_link_blocked.connect(
        lambda url: print(f"Blocked external link: {url}")
    )

    # Set as central widget
    window.setCentralWidget(viewer)
    window.show()

    # Show blank page
    viewer.show_blank_page()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
