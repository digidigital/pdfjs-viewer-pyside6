"""Ultra stability example with comprehensive Chromium flags.

This example demonstrates using the most comprehensive stability settings
available, including all beneficial Chromium flags that don't impact PDF viewing.
"""
import sys
from pathlib import Path

# IMPORTANT: Configure stability BEFORE importing PySide6
from pdfjs_viewer.stability import (
    configure_global_stability,
    get_ultra_stability_chromium_flags,
    print_stability_info
)

# Option 1: Use built-in comprehensive stability (recommended)
configure_global_stability(
    disable_gpu=True,
    disable_webgl=True,
    disable_gpu_compositing=True,
    disable_unnecessary_features=True,  # Disables audio, WebRTC, notifications, etc.
)

# Option 2: Add even more flags for maximum stability (optional)
# Uncomment to enable:
# configure_global_stability(
#     disable_gpu=True,
#     disable_webgl=True,
#     disable_unnecessary_features=True,
#     extra_args=get_ultra_stability_chromium_flags()
# )

# Now import Qt after stability configuration
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PySide6.QtCore import Qt

from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig, PDFStabilityConfig


class UltraStabilityWindow(QMainWindow):
    """Window demonstrating ultra-stable PDF viewing."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ultra Stability PDF Viewer")
        self.resize(1200, 800)

        # Create main widget
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Info label
        info_label = QLabel(
            "<b>Ultra Stability Configuration Active</b><br>"
            "This viewer has maximum crash prevention enabled:<br>"
            "• All GPU features disabled<br>"
            "• WebGL/WebGL2 disabled<br>"
            "• Audio/WebRTC disabled<br>"
            "• Background networking disabled<br>"
            "• All unnecessary features disabled<br>"
            "• Profile isolation enabled<br>"
            "• Automatic crash recovery enabled"
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("padding: 10px")
        layout.addWidget(info_label)

        # Create viewer with maximum stability config
        config = PDFViewerConfig(
            stability=PDFStabilityConfig(
                use_isolated_profile=True,
                disable_webgl=True,
                disable_gpu=True,
                disable_gpu_compositing=True,
                disable_cache=True,
                disable_local_storage=True,
                disable_session_storage=True,
                disable_databases=True,
                disable_service_workers=True,
                disable_background_networking=True,
                max_cache_size_mb=0,
                safer_mode=True,
            )
        )
        config.features.load_enabled = True
        
        self.viewer = PDFViewerWidget(config=config)
        layout.addWidget(self.viewer, stretch=1)

        # Load button
        load_btn = QPushButton("Load PDF")
        load_btn.clicked.connect(self._load_sample)
        layout.addWidget(load_btn)

        self.setCentralWidget(main_widget)

        # Show blank page initially
        self.viewer.show_blank_page()

    def _load_sample(self):
        """Load a sample PDF or show file dialog."""
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF File",
            str(Path.home()),
            "PDF Files (*.pdf);;All Files (*)"
        )

        if file_path:
            try:
                self.viewer.load_pdf(file_path)
            except Exception as e:
                print(f"Error loading PDF: {e}")


def main():
    # Print current stability configuration
    print_stability_info()
    print()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = UltraStabilityWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
