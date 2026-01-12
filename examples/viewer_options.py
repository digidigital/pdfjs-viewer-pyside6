"""PDF.js Viewer Options Example.

Demonstrates how to use viewer options (page, zoom, pagemode, nameddest)
when loading PDF files.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSpinBox, QComboBox, QLabel, QGroupBox, QFileDialog
)
from PySide6.QtCore import Qt

from pdfjs_viewer import PDFViewerWidget, ConfigPresets


class ViewerOptionsDemo(QMainWindow):
    """Demo showing PDF.js viewer options in action."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF.js Viewer - Viewer Options Demo")
        self.resize(1400, 900)

        # Create main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # PDF viewer (left side, 70% width)
        self.viewer = PDFViewerWidget(config=ConfigPresets.unrestricted())
        main_layout.addWidget(self.viewer, stretch=7)

        # Control panel (right side, 30% width)
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel, stretch=3)

        # Connect signals
        self.viewer.pdf_loaded.connect(self._on_pdf_loaded)
        self.viewer.error_occurred.connect(lambda msg: print(f"Error: {msg}"))

        # Store current PDF path
        self.current_pdf_path = None
        
        # Show blank page initially
        self.viewer.show_blank_page()

    def _create_control_panel(self) -> QWidget:
        """Create the control panel with viewer options."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # File selection
        file_group = QGroupBox("PDF File")
        file_layout = QVBoxLayout(file_group)

        select_btn = QPushButton("Select PDF File...")
        select_btn.clicked.connect(self._select_pdf)
        file_layout.addWidget(select_btn)

        self.file_label = QLabel("No file selected")
        self.file_label.setWordWrap(True)
        file_layout.addWidget(self.file_label)

        layout.addWidget(file_group)

        # Viewer options
        options_group = QGroupBox("Viewer Options")
        options_layout = QVBoxLayout(options_group)

        # Page number
        page_layout = QHBoxLayout()
        page_layout.addWidget(QLabel("Page:"))
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(9999)
        self.page_spin.setValue(1)
        self.page_spin.setToolTip("Page number to open (1-indexed)")
        page_layout.addWidget(self.page_spin)
        options_layout.addLayout(page_layout)

        # Zoom level
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems([
            "auto",
            "page-width",
            "page-height",
            "page-fit",
            "50%",
            "75%",
            "100%",
            "125%",
            "150%",
            "200%",
        ])
        self.zoom_combo.setCurrentText("page-fit")
        self.zoom_combo.setToolTip("Zoom level (named or percentage)")
        zoom_layout.addWidget(self.zoom_combo)
        options_layout.addLayout(zoom_layout)

        # Page mode (sidebar)
        pagemode_layout = QHBoxLayout()
        pagemode_layout.addWidget(QLabel("Sidebar:"))
        self.pagemode_combo = QComboBox()
        self.pagemode_combo.addItems([
            "none",
            "thumbs",
            "bookmarks",
            "attachments",
        ])
        self.pagemode_combo.setCurrentText("none")
        self.pagemode_combo.setToolTip("Sidebar state")
        pagemode_layout.addWidget(self.pagemode_combo)
        options_layout.addLayout(pagemode_layout)

        layout.addWidget(options_group)

        # Load button
        load_btn = QPushButton("Load PDF with Options")
        load_btn.clicked.connect(self._load_with_options)
        load_btn.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(load_btn)

        # Presets group
        presets_group = QGroupBox("Quick Presets")
        presets_layout = QVBoxLayout(presets_group)

        presets = [
            ("First Page, Page Width", 1, "page-width", "none"),
            ("Page 5, Fit to Page", 5, "page-fit", "none"),
            ("Page 10, Thumbnails", 10, "page-fit", "thumbs"),
            ("Page 1, Bookmarks", 1, "auto", "bookmarks"),
            ("Page 3, 150% Zoom", 3, "150", "none"),
        ]

        for name, page, zoom, pagemode in presets:
            btn = QPushButton(name)
            btn.clicked.connect(
                lambda checked, p=page, z=zoom, pm=pagemode: self._apply_preset(p, z, pm)
            )
            presets_layout.addWidget(btn)

        layout.addWidget(presets_group)

        # Info section
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout(info_group)

        info_text = QLabel(
            "<b>Supported Options:</b><br>"
            "• <b>page</b>: Page number (1-indexed)<br>"
            "• <b>zoom</b>: Named modes or percentage<br>"
            "  - Named: auto, page-width, page-height, page-fit<br>"
            "  - Numeric: 10-1000 (percentage)<br>"
            "• <b>pagemode</b>: Sidebar state<br>"
            "  - none, thumbs, bookmarks, attachments<br><br>"
            "<i>Options are applied when PDF is loaded.</i>"
        )
        info_text.setWordWrap(True)
        info_text.setAlignment(Qt.AlignmentFlag.AlignTop)
        info_layout.addWidget(info_text)

        layout.addWidget(info_group)

        layout.addStretch()
        return panel

    def _select_pdf(self):
        """Open file dialog to select a PDF."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PDF File",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )

        if file_path:
            self.current_pdf_path = file_path
            self.file_label.setText(f"Selected: {Path(file_path).name}")

    def _load_with_options(self):
        """Load PDF with current option settings."""
        if not self.current_pdf_path:
            self.file_label.setText("Please select a PDF file first")
            return

        # Get option values
        page = self.page_spin.value()
        zoom_text = self.zoom_combo.currentText()
        pagemode = self.pagemode_combo.currentText()

        # Convert zoom text to appropriate type
        if zoom_text.endswith('%'):
            zoom = int(zoom_text[:-1])  # Remove % and convert to int
        else:
            zoom = zoom_text  # Named mode (string)

        print(f"Loading PDF: {self.current_pdf_path}")
        print(f"  page={page}, zoom={zoom}, pagemode={pagemode}")

        # Load with options
        try:
            self.viewer.load_pdf(
                self.current_pdf_path,
                page=page,
                zoom=zoom,
                pagemode=pagemode
            )
        except Exception as e:
            print(f"Error loading PDF: {e}")
            self.file_label.setText(f"Error: {e}")

    def _apply_preset(self, page: int, zoom: str, pagemode: str):
        """Apply a preset configuration."""
        self.page_spin.setValue(page)

        # Handle zoom - could be percentage string or named mode
        if zoom.isdigit():
            zoom = f"{zoom}%"
        self.zoom_combo.setCurrentText(zoom)

        self.pagemode_combo.setCurrentText(pagemode)

        # Auto-load if PDF is selected
        if self.current_pdf_path:
            self._load_with_options()

    def _on_pdf_loaded(self, metadata: dict):
        """Handle PDF loaded event."""
        filename = metadata.get('filename', 'Unknown')
        num_pages = metadata.get('numPages', 0)
        print(f"PDF loaded: {filename}, {num_pages} pages")

        # Update page spinner maximum
        if num_pages > 0:
            self.page_spin.setMaximum(num_pages)


def main():
    app = QApplication(sys.argv)

    window = ViewerOptionsDemo()
    window.show()

    # Load example PDF if available
    example_pdf = Path(__file__).parent.parent / "tests" / "data" / "sample.pdf"
    if example_pdf.exists():
        window.current_pdf_path = str(example_pdf)
        window.file_label.setText(f"Selected: {example_pdf.name}")
        # Load at page 1 with page-fit zoom
        window.viewer.load_pdf(str(example_pdf), page=1, zoom="page-fit")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
