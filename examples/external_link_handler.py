"""External link handling demonstration.

This example shows how to handle external links clicked in PDFs, including:
1. Blocking external links for security
2. Asking user before opening (built-in confirmation dialog)
3. Allowing all external links without confirmation
"""
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QLabel, QTextEdit, QGroupBox, QRadioButton, QMessageBox,
    QFileDialog
)
from PySide6.QtCore import Qt

from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig, PDFSecurityConfig


class ExternalLinkHandlerWindow(QMainWindow):
    """Window demonstrating external link handling strategies."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("External Link Handler Demo")
        self.resize(1400, 900)

        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)

        # Info label
        info_label = QLabel(
            "<b>External Link Handling Demo</b><br>"
            "Load a PDF with external links and click them to see different handling strategies."
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("padding: 10px;")
        main_layout.addWidget(info_label)

        # Control panel
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)

        # PDF viewer
        self.viewer = None
        self._create_viewer_blocking()  # Start with blocking mode
        main_layout.addWidget(self.viewer, stretch=1)

        # Event log
        log_label = QLabel("<b>Event Log:</b>")
        main_layout.addWidget(log_label)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        main_layout.addWidget(self.log)

        # Load button
        load_btn = QPushButton("Load PDF")
        load_btn.clicked.connect(self._load_pdf)
        main_layout.addWidget(load_btn)

        self.setCentralWidget(main_widget)

    def _create_control_panel(self) -> QWidget:
        """Create control panel for link handling mode."""
        panel = QGroupBox("Link Handling Strategy")
        layout = QVBoxLayout()

        # Radio buttons for different strategies
        self.block_radio = QRadioButton("Block All External Links (Security)")
        self.block_radio.setChecked(True)
        self.block_radio.toggled.connect(self._on_mode_changed)
        layout.addWidget(self.block_radio)

        self.ask_radio = QRadioButton("Ask Before Opening (Built-in Confirmation)")
        self.ask_radio.toggled.connect(self._on_mode_changed)
        layout.addWidget(self.ask_radio)

        self.allow_radio = QRadioButton("Allow All External Links (No Confirmation)")
        self.allow_radio.toggled.connect(self._on_mode_changed)
        layout.addWidget(self.allow_radio)

        # Description
        desc_label = QLabel(
            "<small>"
            "<b>Block:</b> All external links are blocked and logged<br>"
            "<b>Ask:</b> Built-in confirmation dialog before opening each link<br>"
            "<b>Allow:</b> Links open automatically in external browser"
            "</small>"
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        panel.setLayout(layout)
        return panel

    def _on_mode_changed(self):
        """Handle link handling mode change."""
        if self.block_radio.isChecked():
            self._log("Mode: Blocking all external links")
            self._recreate_viewer_blocking()
        elif self.ask_radio.isChecked():
            self._log("Mode: Asking before opening links (built-in dialog)")
            self._recreate_viewer_ask()
        elif self.allow_radio.isChecked():
            self._log("Mode: Allowing all external links")
            self._recreate_viewer_allow()

    def _create_viewer_blocking(self):
        """Create viewer that blocks external links."""
        config = PDFViewerConfig(
            security=PDFSecurityConfig(
                allow_external_links=False,  # Block external links
                block_remote_content=True,   # Also block remote resources
            )
        )
        config.features.load_enabled = True

        self.viewer = PDFViewerWidget(config=config)

        # Connect signal to log blocked links
        self.viewer.external_link_blocked.connect(self._on_external_link_blocked)

        # Show blank page initially
        self.viewer.show_blank_page()

    def _recreate_viewer_blocking(self):
        """Recreate viewer with blocking configuration."""
        self._remove_viewer()

        config = PDFViewerConfig(
            security=PDFSecurityConfig(
                allow_external_links=False,
                block_remote_content=True,
            )
        )
        config.features.load_enabled = True

        self.viewer = PDFViewerWidget(config=config)
        self.viewer.external_link_blocked.connect(self._on_external_link_blocked)

        self._insert_viewer()

    def _recreate_viewer_ask(self):
        """Recreate viewer with ask-before-opening configuration.

        Uses the built-in confirm_before_external_link feature.
        """
        self._remove_viewer()

        config = PDFViewerConfig(
            security=PDFSecurityConfig(
                allow_external_links=True,   # Allow links (with confirmation)
                confirm_before_external_link=True,  # Show built-in confirmation dialog
                block_remote_content=True,
                allowed_protocols=["mailto", "http", "https"],
            ),
        )
        config.features.load_enabled = True

        self.viewer = PDFViewerWidget(config=config)

        self._insert_viewer()

    def _recreate_viewer_allow(self):
        """Recreate viewer that allows all external links without confirmation."""
        self._remove_viewer()

        config = PDFViewerConfig(
            security=PDFSecurityConfig(
                allow_external_links=True,   # Allow all links
                confirm_before_external_link=False,  # No confirmation dialog
                block_remote_content=False,
            ),
        )
        config.features.load_enabled = True

        self.viewer = PDFViewerWidget(config=config)

        self._insert_viewer()

    def _remove_viewer(self):
        """Remove the current viewer from layout."""
        if self.viewer:
            layout = self.centralWidget().layout()
            layout.removeWidget(self.viewer)
            self.viewer.deleteLater()

    def _insert_viewer(self):
        """Insert viewer into layout and show blank page."""
        layout = self.centralWidget().layout()
        layout.insertWidget(2, self.viewer, stretch=1)
        self.viewer.show_blank_page()

    def _on_external_link_blocked(self, url: str):
        """Handle external link that was blocked.

        This signal is emitted when:
        - allow_external_links=False in security config
        - User clicks an http/https link in the PDF

        Args:
            url: The blocked URL
        """
        self._log(f"External link blocked: {url}")

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
                self.viewer.load_pdf(file_path)
                self._log(f"Loaded: {Path(file_path).name}")
            except Exception as e:
                self._log(f"Error loading PDF: {e}")
                QMessageBox.critical(self, "Load Error", f"Failed to load PDF:\n{e}")

    def _log(self, message: str):
        """Add message to log."""
        self.log.append(message)
        # Auto-scroll to bottom
        self.log.verticalScrollBar().setValue(
            self.log.verticalScrollBar().maximum()
        )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = ExternalLinkHandlerWindow()
    window.show()

    # Show info dialog
    QMessageBox.information(
        window,
        "External Link Handler Demo",
        "<h3>How to Use</h3>"
        "<p>1. Select a link handling strategy from the control panel</p>"
        "<p>2. Load a PDF that contains external links (http/https URLs)</p>"
        "<p>3. Click on external links in the PDF to see how they're handled</p>"
        "<br>"
        "<p><b>Strategies:</b></p>"
        "<ul>"
        "<li><b>Block:</b> Links are blocked and logged (secure)</li>"
        "<li><b>Ask:</b> Built-in confirmation dialog before opening (flexible)</li>"
        "<li><b>Allow:</b> Links open automatically (convenient)</li>"
        "</ul>"
        "<br>"
        "<p><i>Note: Internal PDF links (page navigation) always work regardless "
        "of external link settings.</i></p>"
    )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
