"""Demo of unsaved changes handling modes.

Demonstrates the three unsaved_changes_action modes:
- disabled: No warning, allow navigation (default, backwards compatible)
- prompt: Show dialog with Save As / Save / Discard options
- auto_save: Automatically save annotations before leaving

When you make annotations and then try to:
- Close the window
- Load a new PDF

The viewer will handle unsaved changes according to the configured mode.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QComboBox, QLabel, QFileDialog
)
from pdfjs_viewer import PDFViewerWidget, ConfigPresets


class DemoWindow(QMainWindow):
    """Demo window showing unsaved changes handling."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Unsaved Changes Demo")
        self.resize(1024, 768)
        self.viewer = None  # Will be set in _create_viewer

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Control bar
        controls = QHBoxLayout()

        # Mode selector
        controls.addWidget(QLabel("Unsaved Changes Action:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["disabled", "prompt", "auto_save"])
        self.mode_combo.setCurrentText("prompt")  # Default to prompt for demo
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        controls.addWidget(self.mode_combo)

        controls.addStretch()

        # Open PDF button
        open_btn = QPushButton("Open PDF...")
        open_btn.clicked.connect(self._open_pdf)
        controls.addWidget(open_btn)

        # Check unsaved button
        check_btn = QPushButton("Check Unsaved Changes")
        check_btn.clicked.connect(self._check_unsaved)
        controls.addWidget(check_btn)

        layout.addLayout(controls)

        # Status label
        self.status_label = QLabel("Mode: prompt - Make some annotations, then close or open another PDF")
        layout.addWidget(self.status_label)

        # Create viewer with prompt mode
        self._create_viewer("prompt")

    def _create_viewer(self, mode: str):
        """Create or recreate viewer with specified mode."""
        # Get annotation preset and customize unsaved_changes_action
        config = ConfigPresets.annotation()
        config.features.unsaved_changes_action = mode

        self.viewer = PDFViewerWidget(config=config)

        # Connect signals
        self.viewer.pdf_loaded.connect(
            lambda meta: self.status_label.setText(
                f"Loaded: {meta.get('filename', 'Unknown')} ({meta.get('numPages', 0)} pages)"
            )
        )
        self.viewer.annotation_modified.connect(
            lambda: self.status_label.setText("Annotations modified - try closing the window!")
        )
        self.viewer.error_occurred.connect(
            lambda msg: print(f"Error: {msg}")
        )

        # Add to layout
        if hasattr(self, '_viewer_container'):
            # Remove old viewer
            self.centralWidget().layout().removeWidget(self._viewer_container)
            self._viewer_container.deleteLater()

        self._viewer_container = self.viewer
        self.centralWidget().layout().addWidget(self.viewer)

        # Show blank page initially
        self.viewer.show_blank_page()

    def _on_mode_changed(self, mode: str):
        """Handle mode change - recreate viewer with new mode."""
        self._create_viewer(mode)
        mode_descriptions = {
            "disabled": "No warning - changes will be lost on close",
            "prompt": "Dialog shown with Save As / Save / Discard options",
            "auto_save": "Changes automatically saved to original file"
        }
        self.status_label.setText(f"Mode: {mode} - {mode_descriptions[mode]}")

    def _open_pdf(self):
        """Open a PDF file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF",
            str(Path.home()),
            "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            self.viewer.load_pdf(file_path)

    def _check_unsaved(self):
        """Check if there are unsaved changes."""
        has_changes = self.viewer.has_unsaved_changes()
        if has_changes:
            self.status_label.setText("Has unsaved changes: YES")
        else:
            self.status_label.setText("Has unsaved changes: NO")

    def closeEvent(self, event):
        """Handle window close - delegate to viewer for unsaved changes check."""
        if self.viewer:
            # The viewer's handle_unsaved_changes will show dialog if needed
            if not self.viewer.handle_unsaved_changes():
                event.ignore()
                return
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)

    window = DemoWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
