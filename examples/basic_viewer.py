"""Basic PDF viewer example.

Demonstrates minimal setup for viewing a PDF file with unrestricted features,
plus examples of customizing presets for features and security.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow
from pdfjs_viewer import PDFViewerWidget, ConfigPresets


def main():
    app = QApplication(sys.argv)

    # Create main window
    window = QMainWindow()
    window.setWindowTitle("PDF.js Viewer - Basic Example")
    window.resize(1024, 768)

    # ===== EXAMPLE 1: Unrestricted preset (default) =====
    # Create PDF viewer widget with annotation preset
    config = ConfigPresets.annotation()
    viewer = PDFViewerWidget(config=config)
    
    # ===== EXAMPLE 2: Customize preset - Simple approach =====
    # Start with readonly preset but enable saving
    # viewer = PDFViewerWidget(
    #     preset="readonly",
    #     customize={"features": {"save_enabled": True}}
    # )

    # ===== EXAMPLE 3: Customize preset - Features =====
    # Customize multiple feature flags
    # viewer = PDFViewerWidget(
    #     preset="simple",
    #     customize={
    #         "features": {
    #             "save_enabled": True,
    #             "print_enabled": True,
    #             "ink_enabled": True,        # Enable drawing tool
    #             "stamp_enabled": True,      # Enable stamps
    #             "presentation_mode": True,  # Enable fullscreen
    #         }
    #     }
    # )

    # ===== EXAMPLE 4: Customize preset - Security =====
    # Configure security settings
    # viewer = PDFViewerWidget(
    #     preset="annotation",
    #     customize={
    #         "security": {
    #             "allow_external_links": True,      # Allow links in PDFs
    #             "block_remote_content": False,     # Allow remote images
    #             "allowed_protocols": ["http", "https", "mailto"],
    #         }
    #     }
    # )

    # ===== EXAMPLE 5: Global stability settings =====
    # Configure stability for embedded/crash-prone systems.
    # NOTE: configure_global_stability() must be called BEFORE QApplication creation.
    # from pdfjs_viewer.stability import configure_global_stability
    # configure_global_stability(
    #     disable_gpu=True,
    #     disable_webgl=True,
    #     disable_gpu_compositing=True,
    # )
    # app = QApplication(sys.argv)  # Must come after configure_global_stability()

    # ===== EXAMPLE 6: Customize features and security together =====
    # Combined customization of features and security
    # viewer = PDFViewerWidget(
    #     preset="simple",
    #     customize={
    #         "features": {
    #             "highlight_enabled": True,
    #             "freetext_enabled": True,
    #             "ink_enabled": True,
    #         },
    #         "security": {
    #             "allow_external_links": False,
    #             "block_remote_content": True,
    #         },
    #     }
    # )

    # Connect signals
    viewer.pdf_loaded.connect(
        lambda meta: print(f"PDF loaded: {meta.get('filename', 'Unknown')}, "
                          f"{meta.get('numPages', 0)} pages")
    )

    viewer.error_occurred.connect(
        lambda msg: print(f"Error: {msg}")
    )
    
    # Set as central widget
    window.setCentralWidget(viewer)
    
    # Show window
    window.show()

    # Show blank viewer
    viewer.show_blank_page()
    
    # Or Load a PDF (replace with your PDF path)
    # viewer.load_pdf("sample.pdf") 

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
