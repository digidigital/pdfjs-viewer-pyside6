"""Feature selection example.

Demonstrates dynamic feature configuration with interactive controls.
Shows all available feature toggles with a reload button to apply changes.

Layout: PDF viewer on left, feature controls on right side.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QCheckBox, QPushButton, QScrollArea
)
from PySide6.QtCore import Qt
from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig, PDFFeatures


class FeatureSelectionWindow(QMainWindow):
    """Main window with PDF viewer and feature controls."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF.js Viewer - Feature Selection")
        self.resize(1400, 900)

        # Create main widget and layout (horizontal: viewer left, controls right)
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Create PDF viewer with default config (left side)
        self.viewer = PDFViewerWidget()
        main_layout.addWidget(self.viewer, stretch=4)

        # Create control panel (right side)
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(10)

        # Title label
        title_label = QGroupBox("Feature Configuration")
        title_label.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #0078d4;
                border: none;
            }
        """)
        control_layout.addWidget(title_label)

        # Create scrollable settings panel
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        settings_scroll.setMinimumWidth(300)
        settings_scroll.setMaximumWidth(400)

        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(5, 5, 5, 5)
        settings_layout.setSpacing(15)

        # Create feature checkboxes organized in groups
        self.checkboxes = {}

        # Core Actions group
        core_group = self._create_feature_group(
            "Core Actions",
            [
                ("print_enabled", "Print", True),
                ("save_enabled", "Save/Download", True),
                ("load_enabled", "Load File", True),
                ("presentation_mode", "Presentation Mode", True),
            ]
        )
        settings_layout.addWidget(core_group)

        # Annotation Tools group (without signature and comment)
        annotation_group = self._create_feature_group(
            "Annotation Tools",
            [
                ("highlight_enabled", "Highlight", True),
                ("freetext_enabled", "Free Text", True),
                ("ink_enabled", "Ink/Draw", True),
                ("stamp_enabled", "Stamp", True),
            ]
        )
        settings_layout.addWidget(annotation_group)

        # Navigation group
        nav_group = self._create_feature_group(
            "Navigation & View",
            [
                ("bookmark_enabled", "Bookmark", True),
                ("scroll_mode_buttons", "Scroll Mode Buttons", True),
                ("spread_mode_buttons", "Spread Mode Buttons", True),
            ]
        )
        settings_layout.addWidget(nav_group)

        settings_layout.addStretch()

        settings_scroll.setWidget(settings_widget)
        control_layout.addWidget(settings_scroll)

        # Reload button
        self.reload_button = QPushButton("🔄 Reload Viewer")
        self.reload_button.setMinimumHeight(45)
        self.reload_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.reload_button.clicked.connect(self._reload_viewer)
        control_layout.addWidget(self.reload_button)

        # Add control panel to main layout
        main_layout.addWidget(control_panel, stretch=1)

        # Set central widget
        self.setCentralWidget(main_widget)

        # Connect viewer signals
        self.viewer.pdf_loaded.connect(
            lambda meta: print(f"PDF loaded: {meta.get('filename', 'Unknown')}, "
                              f"{meta.get('numPages', 0)} pages")
        )
        self.viewer.error_occurred.connect(
            lambda msg: print(f"Error: {msg}")
        )

        # Show blank page initially
        self.viewer.show_blank_page()

    def _create_feature_group(self, title: str, features: list) -> QGroupBox:
        """Create a group box with feature checkboxes.

        Args:
            title: Group box title
            features: List of (config_key, label, default_checked) tuples

        Returns:
            QGroupBox with checkboxes
        """
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #d0d0d0;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #0078d4;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(8)

        for config_key, label, default_checked in features:
            checkbox = QCheckBox(label)
            checkbox.setChecked(default_checked)
            checkbox.setStyleSheet("font-weight: normal;")
            self.checkboxes[config_key] = checkbox
            layout.addWidget(checkbox)

        group.setLayout(layout)
        return group

    def _reload_viewer(self):
        """Reload the PDF viewer with current feature selection."""
        print("Reloading viewer with selected features...")

        # Build configuration from checkboxes
        features = PDFFeatures(
            # Core actions
            print_enabled=self.checkboxes["print_enabled"].isChecked(),
            save_enabled=self.checkboxes["save_enabled"].isChecked(),
            load_enabled=self.checkboxes["load_enabled"].isChecked(),
            presentation_mode=self.checkboxes["presentation_mode"].isChecked(),

            # Annotation tools (signature and comment not exposed in UI)
            highlight_enabled=self.checkboxes["highlight_enabled"].isChecked(),
            freetext_enabled=self.checkboxes["freetext_enabled"].isChecked(),
            ink_enabled=self.checkboxes["ink_enabled"].isChecked(),
            stamp_enabled=self.checkboxes["stamp_enabled"].isChecked(),

            # Navigation
            bookmark_enabled=self.checkboxes["bookmark_enabled"].isChecked(),
            scroll_mode_buttons=self.checkboxes["scroll_mode_buttons"].isChecked(),
            spread_mode_buttons=self.checkboxes["spread_mode_buttons"].isChecked(),
        )

        config = PDFViewerConfig(features=features)

        # Get the current layout
        central_widget = self.centralWidget()
        layout = central_widget.layout()

        # Properly clean up old viewer to prevent profile deletion warning
        old_viewer = self.viewer
        layout.removeWidget(old_viewer)

        # Ensure WebEnginePage is deleted before profile is released
        if hasattr(old_viewer, 'backend'):
            backend = old_viewer.backend
            if hasattr(backend, 'web_view') and backend.web_view:
                # Delete the page first
                page = backend.web_view.page()
                if page:
                    backend.web_view.setPage(None)
                    page.deleteLater()

        old_viewer.setParent(None)
        old_viewer.deleteLater()

        # Process events to ensure deletion completes
        QApplication.processEvents()

        # Create new viewer with updated config
        self.viewer = PDFViewerWidget(config=config)

        # Reconnect signals
        self.viewer.pdf_loaded.connect(
            lambda meta: print(f"PDF loaded: {meta.get('filename', 'Unknown')}, "
                              f"{meta.get('numPages', 0)} pages")
        )
        self.viewer.error_occurred.connect(
            lambda msg: print(f"Error: {msg}")
        )

        # Insert new viewer at position 0 (left side, before control panel)
        layout.insertWidget(0, self.viewer, stretch=4)

        # Show blank page
        self.viewer.show_blank_page()

        print("Viewer reloaded successfully!")

        # Print enabled features
        enabled_features = [key for key, cb in self.checkboxes.items() if cb.isChecked()]
        print(f"Enabled features: {', '.join(enabled_features)}")


def main():
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    window = FeatureSelectionWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
