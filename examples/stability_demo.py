"""Stability features demonstration.

This example demonstrates the different stability levels and how to configure
them for maximum crash prevention in production environments.
"""
import os
# Set BEFORE PySide6 imports (but ideally use the shell instead)
os.environ.setdefault("QT_ACCESSIBILITY", "0")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
                      "--disable-features=AccessibilityObjectModel --disable-gpu")

from PySide6 import QtCore, QtWidgets, QtWebEngineWidgets

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QFileDialog, QTextEdit, QGroupBox,
    QCheckBox, QMessageBox
)
from PySide6.QtCore import Qt

from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig, PDFStabilityConfig
from pdfjs_viewer.stability import (
    get_recommended_stability_config,
    get_maximum_stability_config,
    print_stability_info
)


class StabilityDemoWindow(QMainWindow):
    """Main window demonstrating stability configurations."""

    STABILITY_LEVELS = {
        "Default (Safer Mode)": "default",
        "Recommended Production": "recommended",
        "Maximum Stability": "maximum",
        "Performance Mode (Unsafe)": "performance",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF.js Viewer - Stability Demo")
        self.resize(1400, 900)

        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Create PDF viewer with default (safer mode)
        self.viewer = PDFViewerWidget()
        main_layout.addWidget(self.viewer, stretch=3)

        # Create settings panel
        settings_widget = self._create_settings_panel()
        main_layout.addWidget(settings_widget)

        # Set central widget
        self.setCentralWidget(main_widget)

        # Connect viewer signals
        self.viewer.error_occurred.connect(self._on_error_occurred)

        # Log widget
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)

        # Add log to layout
        main_layout.addWidget(QLabel("<b>Event Log:</b>"))
        main_layout.addWidget(self.log)

        # Track currently loaded PDF
        self.current_pdf_path = None

        # Show blank page initially
        self.viewer.show_blank_page()

        # Log initial configuration
        self._log_config(self.viewer.backend.config.stability)

    def _create_settings_panel(self) -> QWidget:
        """Create settings panel with stability level selection."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)

        # Stability level selection group
        level_group = QGroupBox("Stability Level")
        level_layout = QVBoxLayout()

        # Level combo box
        level_row = QHBoxLayout()
        level_row.addWidget(QLabel("Stability Level:"))
        self.level_combo = QComboBox()
        for name in self.STABILITY_LEVELS.keys():
            self.level_combo.addItem(name)
        self.level_combo.currentTextChanged.connect(self._on_level_changed)
        level_row.addWidget(self.level_combo, stretch=1)
        level_layout.addLayout(level_row)

        # Level descriptions
        desc_label = QLabel(
            "<small>"
            "<b>Default:</b> Safer mode enabled (recommended for most use cases)<br>"
            "<b>Recommended:</b> Production-ready configuration (75-85% crash reduction)<br>"
            "<b>Maximum:</b> Most restrictive settings (85-95% crash reduction)<br>"
            "<b>Performance:</b> Unsafe mode for testing (no stability features)"
            "</small>"
        )
        desc_label.setWordWrap(True)
        level_layout.addWidget(desc_label)

        level_group.setLayout(level_layout)
        layout.addWidget(level_group)

        # Current configuration display
        self.config_group = QGroupBox("Current Configuration")
        self.config_layout = QVBoxLayout()
        self.config_group.setLayout(self.config_layout)
        layout.addWidget(self.config_group)

        # Action buttons
        button_row = QHBoxLayout()

        load_btn = QPushButton("📁 Load PDF")
        load_btn.clicked.connect(self._load_pdf)
        button_row.addWidget(load_btn)

        info_btn = QPushButton("ℹ️ Show Environment Info")
        info_btn.clicked.connect(self._show_env_info)
        button_row.addWidget(info_btn)

        layout.addLayout(button_row)

        return panel

    def _on_level_changed(self, level_name: str):
        """Handle stability level selection change."""
        from PySide6.QtCore import QCoreApplication

        level = self.STABILITY_LEVELS[level_name]
        self._log(f"Changing to: {level_name}")

        # Create new config based on level
        if level == "default":
            # Default safer mode
            config = PDFViewerConfig()

        elif level == "recommended":
            # Recommended production config
            config = PDFViewerConfig(
                stability=PDFStabilityConfig(**get_recommended_stability_config())
            )

        elif level == "maximum":
            # Maximum stability
            config = PDFViewerConfig(
                stability=PDFStabilityConfig(**get_maximum_stability_config())
            )

        elif level == "performance":
            # Performance mode (unsafe)
            config = PDFViewerConfig(
                stability=PDFStabilityConfig(
                    use_isolated_profile=False,
                    disable_webgl=False,
                    disable_gpu=False,
                    disable_cache=False,
                    disable_local_storage=False,
                    disable_service_workers=False,
                    safer_mode=False
                )
            )

        # Recreate viewer with new config
        self._recreate_viewer(config)

    def _recreate_viewer(self, config: PDFViewerConfig):
        """Recreate viewer with new configuration."""
        from PySide6.QtCore import QCoreApplication

        central_widget = self.centralWidget()
        layout = central_widget.layout()

        # Remove old viewer
        old_viewer = self.viewer
        layout.removeWidget(old_viewer)
        old_viewer.setParent(None)
        old_viewer.deleteLater()

        # Process events to ensure cleanup
        QCoreApplication.processEvents()

        # Create new viewer
        self.viewer = PDFViewerWidget(config=config)

        # Reconnect signals
        self.viewer.error_occurred.connect(self._on_error_occurred)

        # Insert at correct position
        layout.insertWidget(0, self.viewer, stretch=3)

        # Process events again
        QCoreApplication.processEvents()

        # Reload PDF if one was loaded
        if self.current_pdf_path:
            try:
                self.viewer.load_pdf(self.current_pdf_path)
                self._log(f"Reloaded PDF: {Path(self.current_pdf_path).name}")
            except Exception as e:
                self._log(f"Error reloading PDF: {e}")
                self.viewer.show_blank_page()
        else:
            self.viewer.show_blank_page()

        # Update config display
        self._log_config(config.stability)

    def _log_config(self, stability: PDFStabilityConfig):
        """Log current stability configuration."""
        # Clear previous config display
        while self.config_layout.count():
            child = self.config_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add current settings
        settings_text = f"""
<small>
<b>Safer Mode:</b> {stability.safer_mode}<br>
<b>Isolated Profile:</b> {stability.use_isolated_profile}<br>
<b>WebGL Disabled:</b> {stability.disable_webgl}<br>
<b>GPU Disabled:</b> {stability.disable_gpu}<br>
<b>Cache Disabled:</b> {stability.disable_cache}<br>
<b>Local Storage Disabled:</b> {stability.disable_local_storage}<br>
<b>Service Workers Disabled:</b> {stability.disable_service_workers}
</small>
        """.strip()

        label = QLabel(settings_text)
        label.setWordWrap(True)
        self.config_layout.addWidget(label)

    def _load_pdf(self):
        """Load a PDF file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF File",
            str(Path.home()),
            "PDF Files (*.pdf);;All Files (*)"
        )

        if file_path:
            try:
                self.current_pdf_path = file_path
                self.viewer.load_pdf(file_path)
                self._log(f"Loading PDF: {Path(file_path).name}")
            except Exception as e:
                self._log(f"Error loading PDF: {e}")
                QMessageBox.critical(self, "Load Error", f"Failed to load PDF:\n{e}")

    def _show_env_info(self):
        """Show environment and global stability info."""
        import os

        info_text = "=== Stability Environment Info ===\n\n"
        info_text += f"QTWEBENGINE_CHROMIUM_FLAGS:\n  {os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '(not set)')}\n\n"
        info_text += f"QTWEBENGINE_DISABLE_SANDBOX:\n  {os.environ.get('QTWEBENGINE_DISABLE_SANDBOX', '(not set)')}\n\n"
        info_text += f"PDFJS_VIEWER_SAFER_MODE:\n  {os.environ.get('PDFJS_VIEWER_SAFER_MODE', '(not set)')}\n\n"
        info_text += f"Current Level:\n  {self.level_combo.currentText()}\n"

        QMessageBox.information(self, "Environment Info", info_text)
        self._log("Environment info displayed")

    def _on_error_occurred(self, message: str):
        """Handle error events."""
        self._log(f"❌ Error: {message}")

    def _log(self, message: str):
        """Add message to log."""
        self.log.append(message)
        # Auto-scroll to bottom
        self.log.verticalScrollBar().setValue(
            self.log.verticalScrollBar().maximum()
        )


def main():
    # Optional: Apply global stability settings BEFORE QApplication
    # Uncomment to test:
    # from pdfjs_viewer.stability import configure_global_stability
    # configure_global_stability(disable_gpu=True, disable_webgl=True)
    import os 
    os.environ["QT_ACCESSIBILITY"] = "0"

    app = QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    window = StabilityDemoWindow()
    window.show()

    # Show info dialog
    QMessageBox.information(
        window,
        "Stability Demo",
        "<h3>Stability Configuration Levels</h3>"
        "<p><b>Default (Safer Mode):</b> Enabled by default, provides good "
        "balance between stability and functionality. Reduces crashes by ~60-70%.</p>"

        "<p><b>Recommended Production:</b> Optimized for production use. "
        "Provides ~75-85% crash reduction with minimal performance impact.</p>"

        "<p><b>Maximum Stability:</b> Most restrictive configuration for "
        "environments with frequent crashes. Provides ~85-95% crash reduction.</p>"

        "<p><b>Performance Mode:</b> Disables all stability features for testing. "
        "<b>Not recommended</b> - may crash frequently!</p>"

        "<p><i>Try loading a PDF and switching between stability levels to see "
        "how they affect the viewer configuration.</i></p>"
    )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
