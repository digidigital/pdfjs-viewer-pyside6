"""Development and Debug Viewer - THE testing tool for pdfjs-viewer.

This comprehensive testing tool provides:
- Verbose debug logging of all operations
- Version information display
- Custom PDF.js path support
- All signals monitored
- Unrestricted feature access
"""

import sys
import json
from pathlib import Path
from datetime import datetime

from PySide6 import QtCore
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QGroupBox, QFileDialog, QLineEdit,
    QSplitter
)
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtCore import Qt, QTimer

from pdfjs_viewer import PDFViewerWidget, ConfigPresets


class DebugConsole(QTextEdit):
    """Console widget for debug output."""

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setMaximumHeight(250)

        # Style as console
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Courier New', monospace;
                font-size: 10pt;
            }
        """)

    def log(self, message: str, level: str = "INFO"):
        """Add a log message with timestamp and level."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # Color codes for different levels
        colors = {
            "INFO": "#4ec9b0",
            "WARNING": "#dcdcaa",
            "ERROR": "#f48771",
            "SUCCESS": "#4fc1ff",
            "SIGNAL": "#c586c0",
            "JS": "#9cdcfe",
        }

        color = colors.get(level, "#d4d4d4")
        html = f'<span style="color: #858585;">[{timestamp}]</span> '
        html += f'<span style="color: {color}; font-weight: bold;">[{level}]</span> '
        html += f'<span style="color: #d4d4d4;">{message}</span>'

        self.append(html)

        # Auto-scroll to bottom
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class DevDebugViewer(QMainWindow):
    """Comprehensive development and debugging viewer."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DEV AND DEBUG VIEWER - pdfjs-viewer Testing Tool")
        self.resize(1600, 1000)

        # Custom PDF.js path (None = use bundled)
        self.custom_pdfjs_path = None

        # Setup UI
        self._setup_ui()

        # Output version information
        self._output_version_info()

        # Create viewer with unrestricted preset
        self._create_viewer()

    def _setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create console first (needed by control panel)
        self.console = DebugConsole()

        # Create splitter for viewer and console
        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)

        # Top section: Viewer and controls
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        splitter.addWidget(top_widget)

        # PDF Viewer (left, 70%)
        self.viewer_container = QVBoxLayout()
        top_layout.addLayout(self.viewer_container, stretch=7)

        # Control Panel (right, 30%)
        control_panel = self._create_control_panel()
        top_layout.addWidget(control_panel, stretch=3)

        # Bottom section: Debug console
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        splitter.addWidget(console_widget)

        console_label = QLabel("Debug Console (All Operations Logged)")
        console_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        console_layout.addWidget(console_label)

        console_layout.addWidget(self.console)

        # Set splitter sizes (70% viewer, 30% console)
        splitter.setSizes([700, 300])

    def _create_control_panel(self) -> QWidget:
        """Create the control panel with all options."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Version Info Group
        version_group = QGroupBox("Version Information")
        version_layout = QVBoxLayout(version_group)
        self.version_label = QLabel("Loading version info...")
        self.version_label.setWordWrap(True)
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        version_layout.addWidget(self.version_label)
        layout.addWidget(version_group)

        # Custom PDF.js Path Group
        pdfjs_group = QGroupBox("Custom PDF.js Path (Optional)")
        pdfjs_layout = QVBoxLayout(pdfjs_group)

        pdfjs_info = QLabel("Leave empty to use bundled PDF.js")
        pdfjs_info.setStyleSheet("font-style: italic; color: #666;")
        pdfjs_layout.addWidget(pdfjs_info)

        pdfjs_path_layout = QHBoxLayout()
        self.pdfjs_path_input = QLineEdit()
        self.pdfjs_path_input.setPlaceholderText("/path/to/custom/pdfjs/web")
        pdfjs_path_layout.addWidget(self.pdfjs_path_input)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_pdfjs_path)
        pdfjs_path_layout.addWidget(browse_btn)
        pdfjs_layout.addLayout(pdfjs_path_layout)

        apply_pdfjs_btn = QPushButton("Apply & Reload Viewer")
        apply_pdfjs_btn.clicked.connect(self._apply_custom_pdfjs)
        apply_pdfjs_btn.setStyleSheet("font-weight: bold; padding: 5px;")
        pdfjs_layout.addWidget(apply_pdfjs_btn)

        layout.addWidget(pdfjs_group)

        # Test Actions Group
        actions_group = QGroupBox("Test Actions")
        actions_layout = QVBoxLayout(actions_group)

        load_pdf_btn = QPushButton("Load Test PDF")
        load_pdf_btn.clicked.connect(self._load_test_pdf)
        actions_layout.addWidget(load_pdf_btn)

        load_with_options_btn = QPushButton("Load PDF with Viewer Options")
        load_with_options_btn.clicked.connect(self._load_pdf_with_options)
        actions_layout.addWidget(load_with_options_btn)

        load_default_btn = QPushButton("Load Default")
        load_default_btn.clicked.connect(self._load_default)
        load_default_btn.setToolTip("Load PDF.js default viewer (demo PDF)")
        actions_layout.addWidget(load_default_btn)

        clear_console_btn = QPushButton("Clear Console")
        clear_console_btn.clicked.connect(self.console.clear)
        actions_layout.addWidget(clear_console_btn)

        layout.addWidget(actions_group)

        # Signal Monitor Group
        signals_group = QGroupBox("Signal Monitor")
        signals_layout = QVBoxLayout(signals_group)

        self.signal_status = QLabel(
            "All signals are being monitored.\n"
            "Perform actions to see signal emissions."
        )
        self.signal_status.setWordWrap(True)
        self.signal_status.setStyleSheet("color: #0066cc;")
        signals_layout.addWidget(self.signal_status)

        layout.addWidget(signals_group)

        layout.addStretch()
        return panel

    def _output_version_info(self):
        """Output comprehensive version information."""
        self.console.log("=" * 60, "INFO")
        self.console.log("DEV AND DEBUG VIEWER STARTED", "SUCCESS")
        self.console.log("=" * 60, "INFO")

        # Qt versions
        try:
            qt_version = QtCore.qVersion()
            self.console.log(f"Qt Version: {qt_version}", "INFO")
        except Exception as e:
            self.console.log(f"Failed to get Qt version: {e}", "ERROR")

        # PySide6 version
        try:
            from PySide6 import __version__ as pyside_version
            self.console.log(f"PySide6 Version: {pyside_version}", "INFO")
        except Exception as e:
            self.console.log(f"Failed to get PySide6 version: {e}", "ERROR")

        # pdfjs-viewer version
        try:
            from pdfjs_viewer import __version__ as viewer_version
            self.console.log(f"pdfjs-viewer Version: {viewer_version}", "INFO")
        except Exception as e:
            self.console.log(f"Failed to get pdfjs-viewer version: {e}", "ERROR")

        # PDF.js version (try to read from version.json)
        try:
            from pdfjs_viewer.resources import PDFResourceManager
            resource_mgr = PDFResourceManager()
            pdfjs_root = Path(resource_mgr.pdfjs_root)
            version_file = pdfjs_root / "build" / "pdf.mjs"

            if version_file.exists():
                # Try to extract version from file
                with open(version_file, 'r', encoding='utf-8') as f:
                    first_lines = ''.join([f.readline() for _ in range(10)])
                    if 'version' in first_lines.lower():
                        import re
                        version_match = re.search(r'version.*?["\'](\d+\.\d+\.\d+)', first_lines, re.IGNORECASE)
                        if version_match:
                            pdfjs_version = version_match.group(1)
                            self.console.log(f"PDF.js Version: {pdfjs_version}", "INFO")
                        else:
                            self.console.log("PDF.js Version: Could not parse", "WARNING")
                    else:
                        self.console.log("PDF.js Version: Could not determine", "WARNING")
            else:
                self.console.log("PDF.js Version: version file not found", "WARNING")
        except Exception as e:
            self.console.log(f"Failed to get PDF.js version: {e}", "ERROR")

        # Python version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        self.console.log(f"Python Version: {python_version}", "INFO")

        # Platform
        import platform
        self.console.log(f"Platform: {platform.system()} {platform.release()}", "INFO")

        self.console.log("=" * 60, "INFO")

        # Update version label
        version_text = f"""
Qt: {QtCore.qVersion()}
PySide6: {getattr(__import__('PySide6'), '__version__', 'Unknown')}
pdfjs-viewer: {getattr(__import__('pdfjs_viewer'), '__version__', 'Unknown')}
Python: {python_version}
Platform: {platform.system()} {platform.release()}
""".strip()
        self.version_label.setText(version_text)

    def _create_viewer(self):
        """Create the PDF viewer with unrestricted preset."""
        self.console.log("Creating PDFViewerWidget with unrestricted preset...", "INFO")

        try:
            # Create config
            config = ConfigPresets.unrestricted()

            # Create viewer
            if self.custom_pdfjs_path:
                self.console.log(f"Using custom PDF.js from: {self.custom_pdfjs_path}", "INFO")
                self.viewer = PDFViewerWidget(config=config, pdfjs_path=self.custom_pdfjs_path)
            else:
                self.console.log("Using bundled PDF.js", "INFO")
                self.viewer = PDFViewerWidget(config=config)

            # Connect all signals
            self._connect_signals()

            # Install JS console message capture
            self._install_js_console_capture()

            # Add to layout
            self.viewer_container.addWidget(self.viewer)

            self.console.log("PDFViewerWidget created successfully", "SUCCESS")
            self.console.log("All features enabled (unrestricted preset)", "SUCCESS")

        except Exception as e:
            self.console.log(f"FAILED to create viewer: {e}", "ERROR")
            import traceback
            self.console.log(traceback.format_exc(), "ERROR")

    def _connect_signals(self):
        """Connect all viewer signals to debug handlers."""
        self.console.log("Connecting all viewer signals...", "INFO")

        self.viewer.pdf_loaded.connect(self._on_pdf_loaded)
        self.viewer.pdf_saved.connect(self._on_pdf_saved)
        self.viewer.print_requested.connect(self._on_print_requested)
        self.viewer.print_data_ready.connect(self._on_print_data_ready)
        self.viewer.annotation_modified.connect(self._on_annotation_modified)
        self.viewer.page_changed.connect(self._on_page_changed)
        self.viewer.error_occurred.connect(self._on_error)
        self.viewer.external_link_blocked.connect(self._on_external_link_blocked)

        self.console.log("All signals connected", "SUCCESS")

    def _install_js_console_capture(self):
        """Install JavaScript console message capture."""
        try:
            # Access the backend's web view
            web_view = self.viewer.backend.web_view
            original_page = web_view.page()

            # Create console message handler
            def console_message_handler(level, message, lineNumber, sourceID):
                level_names = {
                    QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel: "INFO",
                    QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel: "WARN",
                    QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel: "ERROR",
                }
                level_name = level_names.get(level, "UNKNOWN")

                # Format source
                source = Path(sourceID).name if sourceID else "unknown"
                self.console.log(
                    f"[{source}:{lineNumber}] {message}",
                    "JS"
                )

            # Override the console message handler
            original_page.javaScriptConsoleMessage = console_message_handler

            self.console.log("JavaScript console capture installed", "SUCCESS")
        except Exception as e:
            self.console.log(f"Failed to install JS console capture: {e}", "WARNING")

    def _on_pdf_loaded(self, metadata: dict):
        """Handle PDF loaded signal."""
        filename = metadata.get('filename', 'Unknown')
        num_pages = metadata.get('numPages', 0)

        self.console.log(
            f"PDF Loaded: {filename} ({num_pages} pages)",
            "SIGNAL"
        )

        # Log full metadata
        self.console.log(f"Metadata: {json.dumps(metadata, indent=2)}", "INFO")

    def _on_pdf_saved(self, data: bytes, path: str):
        """Handle PDF saved signal."""
        self.console.log(
            f"PDF Saved: {path} ({len(data):,} bytes)",
            "SIGNAL"
        )

    def _on_print_requested(self, data: bytes):
        """Handle print requested signal."""
        self.console.log(
            f"Print Requested: {len(data):,} bytes",
            "SIGNAL"
        )

    def _on_print_data_ready(self, data: bytes, filename: str):
        """Handle print data ready signal."""
        self.console.log(
            f"Print Data Ready: {filename} ({len(data):,} bytes)",
            "SIGNAL"
        )

    def _on_annotation_modified(self):
        """Handle annotation modified signal."""
        self.console.log("Annotation Modified", "SIGNAL")

    def _on_page_changed(self, current: int, total: int):
        """Handle page changed signal."""
        self.console.log(f"Page Changed: {current}/{total}", "SIGNAL")

    def _on_error(self, message: str):
        """Handle error signal."""
        self.console.log(f"ERROR: {message}", "ERROR")

    def _on_external_link_blocked(self, url: str):
        """Handle external link blocked signal."""
        self.console.log(f"External Link Blocked: {url}", "SIGNAL")

    def _browse_pdfjs_path(self):
        """Browse for custom PDF.js path."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select PDF.js Web Directory",
            "",
            QFileDialog.Option.ShowDirsOnly
        )

        if path:
            self.pdfjs_path_input.setText(path)
            self.console.log(f"Selected custom PDF.js path: {path}", "INFO")

    def _apply_custom_pdfjs(self):
        """Apply custom PDF.js path and reload viewer."""
        path = self.pdfjs_path_input.text().strip()

        if path:
            # Validate path
            pdfjs_path = Path(path)
            viewer_html = pdfjs_path / "viewer.html"

            if not viewer_html.exists():
                self.console.log(
                    f"Invalid PDF.js path: viewer.html not found in {path}",
                    "ERROR"
                )
                return

            self.custom_pdfjs_path = path
            self.console.log(f"Custom PDF.js path set to: {path}", "SUCCESS")
        else:
            self.custom_pdfjs_path = None
            self.console.log("Using bundled PDF.js", "INFO")

        # Recreate viewer
        self.console.log("Reloading viewer with new PDF.js...", "INFO")

        # Remove old viewer
        if hasattr(self, 'viewer'):
            self.viewer_container.removeWidget(self.viewer)
            self.viewer.deleteLater()
            QApplication.processEvents()

        # Create new viewer
        self._create_viewer()

    def _load_test_pdf(self):
        """Load a test PDF file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PDF File",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )

        if file_path:
            self.console.log(f"Loading PDF: {file_path}", "INFO")
            try:
                self.viewer.load_pdf(file_path)
                self.console.log("PDF load initiated", "SUCCESS")
            except Exception as e:
                self.console.log(f"Failed to load PDF: {e}", "ERROR")
                import traceback
                self.console.log(traceback.format_exc(), "ERROR")

    def _load_pdf_with_options(self):
        """Load PDF with viewer options (demonstrates new feature)."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PDF File (Will Open at Page 3, 150% Zoom)",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )

        if file_path:
            self.console.log(f"Loading PDF with options: {file_path}", "INFO")
            self.console.log("  page=3, zoom=150, pagemode='bookmarks'", "INFO")

            try:
                self.viewer.load_pdf(
                    file_path,
                    page=3,
                    zoom=150,
                    pagemode="bookmarks"
                )
                self.console.log("PDF load with options initiated", "SUCCESS")
            except Exception as e:
                self.console.log(f"Failed to load PDF: {e}", "ERROR")
                import traceback
                self.console.log(traceback.format_exc(), "ERROR")

    def _load_default(self):
        """Load default PDF.js viewer (shows demo PDF)."""
        self.console.log("Loading default PDF.js viewer...", "INFO")
        try:
            self.viewer.show_blank_page()
            self.console.log("Default viewer loaded (PDF.js demo PDF)", "SUCCESS")
        except Exception as e:
            self.console.log(f"Failed to load default viewer: {e}", "ERROR")


def main():
    app = QApplication(sys.argv)

    window = DevDebugViewer()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
