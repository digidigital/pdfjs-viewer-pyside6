"""Print handlers example.

Demonstrates all three print handler options:
- SYSTEM: Opens PDF with system default viewer
- QT_DIALOG: Shows Qt print dialog with pypdfium2 rendering
- EMIT_SIGNAL: Emits signal with PDF data for custom handling

Allows switching between handlers at runtime to test each approach.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QFileDialog, QTextEdit, QGroupBox,
    QSpinBox, QCheckBox, QMessageBox
)
from PySide6.QtCore import Qt
from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig, PrintHandler


class PrintHandlersWindow(QMainWindow):
    """Main window demonstrating all print handler options."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF.js Viewer - Print Handlers Demo")
        self.resize(1400, 900)

        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Create PDF viewer with default config (SYSTEM handler)
        config = PDFViewerConfig(
            print_handler=PrintHandler.SYSTEM,
            print_dpi=300,
            print_fit_to_page=True,
            print_parallel_pages=4  
        )
        config.features.load_enabled = True
        self.viewer = PDFViewerWidget(config=config)
        main_layout.addWidget(self.viewer, stretch=3)

        # Create settings panel
        settings_widget = self._create_settings_panel()
        main_layout.addWidget(settings_widget)

        # Set central widget
        self.setCentralWidget(main_widget)

        # Connect viewer signals
        self.viewer.pdf_loaded.connect(self._on_pdf_loaded)
        self.viewer.print_requested.connect(self._on_print_requested)
        self.viewer.print_data_ready.connect(self._on_print_data_ready)
        self.viewer.error_occurred.connect(self._on_error_occurred)

        # Log widget
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)

        # Add log to layout
        main_layout.addWidget(QLabel("<b>Event Log:</b>"))
        main_layout.addWidget(self.log)

        # Track currently loaded PDF for reloading after config changes
        self.current_pdf_path = None

        # Show blank page initially
        self.viewer.show_blank_page()

    def _create_settings_panel(self) -> QWidget:
        """Create settings panel with print handler controls."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)

        # Print handler selection group
        handler_group = QGroupBox("Print Handler Selection")
        handler_layout = QVBoxLayout()

        # Handler combo box
        handler_row = QHBoxLayout()
        handler_row.addWidget(QLabel("Print Handler:"))
        self.handler_combo = QComboBox()
        self.handler_combo.addItem("SYSTEM - Open with system PDF viewer", PrintHandler.SYSTEM)
        self.handler_combo.addItem("QT_DIALOG - Qt print dialog (requires pypdfium2)", PrintHandler.QT_DIALOG)
        self.handler_combo.addItem("EMIT_SIGNAL - Emit signal for custom handling", PrintHandler.EMIT_SIGNAL)
        self.handler_combo.currentIndexChanged.connect(self._on_handler_changed)
        handler_row.addWidget(self.handler_combo, stretch=1)
        handler_layout.addLayout(handler_row)

        # Handler descriptions
        desc_label = QLabel(
            "<small>"
            "<b>SYSTEM:</b> Opens PDF in system default viewer (simple, reliable)<br>"
            "<b>QT_DIALOG:</b> Shows Qt print dialog with page selection and preview<br>"
            "<b>EMIT_SIGNAL:</b> Emits print_data_ready signal for custom workflows"
            "</small>"
        )
        desc_label.setWordWrap(True)
        handler_layout.addWidget(desc_label)

        handler_group.setLayout(handler_layout)
        layout.addWidget(handler_group)

        # Qt Dialog settings (only for QT_DIALOG handler)
        self.qt_settings_group = QGroupBox("Qt Print Dialog Settings")
        qt_layout = QVBoxLayout()

        # DPI setting
        dpi_row = QHBoxLayout()
        dpi_row.addWidget(QLabel("Print DPI:"))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setMinimum(72)
        self.dpi_spin.setMaximum(1200)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSingleStep(50)
        self.dpi_spin.valueChanged.connect(self._update_config)
        dpi_row.addWidget(self.dpi_spin)
        dpi_row.addStretch()
        qt_layout.addLayout(dpi_row)

        # Fit to page checkbox
        self.fit_checkbox = QCheckBox("Scale to fit page")
        self.fit_checkbox.setChecked(True)
        self.fit_checkbox.stateChanged.connect(self._update_config)
        qt_layout.addWidget(self.fit_checkbox)

        # Parallel pages setting
        parallel_row = QHBoxLayout()
        parallel_row.addWidget(QLabel("Parallel page rendering:"))
        self.parallel_spin = QSpinBox()
        self.parallel_spin.setMinimum(1)
        self.parallel_spin.setMaximum(16)
        self.parallel_spin.setValue(4)
        self.parallel_spin.valueChanged.connect(self._update_config)
        parallel_row.addWidget(self.parallel_spin)
        parallel_row.addStretch()
        qt_layout.addLayout(parallel_row)

        self.qt_settings_group.setLayout(qt_layout)
        self.qt_settings_group.setEnabled(False)
        layout.addWidget(self.qt_settings_group)

        # Action buttons
        button_row = QHBoxLayout()

        load_btn = QPushButton("📁 Load PDF")
        load_btn.clicked.connect(self._load_pdf)
        button_row.addWidget(load_btn)

        print_btn = QPushButton("🖨️ Print PDF")
        print_btn.clicked.connect(self._trigger_print)
        button_row.addWidget(print_btn)

        save_custom_btn = QPushButton("💾 Save PDF with Annotations")
        save_custom_btn.clicked.connect(self._save_pdf)
        button_row.addWidget(save_custom_btn)

        layout.addLayout(button_row)

        return panel

    def _on_handler_changed(self, index: int):
        """Handle print handler selection change."""
        handler = self.handler_combo.itemData(index)

        # Enable/disable Qt settings based on handler
        self.qt_settings_group.setEnabled(handler == PrintHandler.QT_DIALOG)

        # Update config
        self._update_config()

        self._log(f"Print handler changed to: {handler.upper()}")

    def _update_config(self):
        """Update viewer configuration with current settings."""
        from PySide6.QtCore import QCoreApplication

        handler = self.handler_combo.currentData()

        config = PDFViewerConfig(
            print_handler=handler,
            print_dpi=self.dpi_spin.value(),
            print_fit_to_page=self.fit_checkbox.isChecked(),
            print_parallel_pages=self.parallel_spin.value()
        )
        config.features.load_enabled = True
        
        # Recreate viewer with new config
        central_widget = self.centralWidget()
        layout = central_widget.layout()

        # Remove old viewer
        old_viewer = self.viewer
        layout.removeWidget(old_viewer)
        old_viewer.setParent(None)
        old_viewer.deleteLater()

        # Process events to ensure old viewer and any modal dialogs are fully cleaned up
        # This prevents modal state conflicts when switching handlers
        QCoreApplication.processEvents()

        # Create new viewer
        self.viewer = PDFViewerWidget(config=config)

        # Reconnect signals
        self.viewer.pdf_loaded.connect(self._on_pdf_loaded)
        self.viewer.print_requested.connect(self._on_print_requested)
        self.viewer.print_data_ready.connect(self._on_print_data_ready)
        self.viewer.error_occurred.connect(self._on_error_occurred)

        # Insert at correct position
        layout.insertWidget(0, self.viewer, stretch=3)

        # Process events again to ensure new viewer is fully initialized
        QCoreApplication.processEvents()

        # Show blank page first to ensure viewer is initialized
        self.viewer.show_blank_page()

        # Reload the PDF if one was previously loaded
        # Use QTimer to delay loading until viewer is fully initialized
        if self.current_pdf_path:
            from PySide6.QtCore import QTimer
            pdf_path = self.current_pdf_path

            def delayed_load():
                try:
                    self.viewer.load_pdf(pdf_path)
                    self._log(f"Reloaded PDF: {Path(pdf_path).name}")
                except Exception as e:
                    self._log(f"Error reloading PDF: {e}")

            # Delay 100ms to ensure viewer HTML is fully loaded
            QTimer.singleShot(100, delayed_load)

    def _load_pdf(self):
        """Load a PDF file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF File",
            str(Path.home()),
            "PDF Files (*.pdf);;All Files (*)"
        )

        if file_path:
            self.current_pdf_path = file_path  # Track for reloading after config changes
            self._log(f"Loading PDF: {Path(file_path).name}")

            # Use delayed loading to ensure viewer is ready
            from PySide6.QtCore import QTimer

            def delayed_load():
                try:
                    self.viewer.load_pdf(file_path)
                except Exception as e:
                    self._log(f"Error loading PDF: {e}")
                    QMessageBox.critical(self, "Load Error", f"Failed to load PDF:\n{e}")

            # Small delay to ensure viewer HTML and scripts are fully initialized
            QTimer.singleShot(50, delayed_load)

    def _trigger_print(self):
        """Trigger print action."""
        self._log("Print triggered")
        self.viewer.print_pdf()

    def _save_pdf(self):
        """Save PDF with annotations."""
        self._log("Save triggered")
        self.viewer.save_pdf()

    def _on_pdf_loaded(self, metadata: dict):
        """Handle PDF loaded event."""
        filename = metadata.get('filename', 'Unknown')
        num_pages = metadata.get('numPages', 0)
        self._log(f"✓ PDF loaded: {filename} ({num_pages} pages)")

    def _on_print_requested(self, data: bytes):
        """Handle print_requested signal (SYSTEM/QT_DIALOG handlers)."""
        handler = self.handler_combo.currentData()
        self._log(f"print_requested signal: {len(data)} bytes (handler: {handler})")

    def _on_print_data_ready(self, data: bytes, filename: str):
        """Handle print_data_ready signal (EMIT_SIGNAL handler)."""
        self._log(f"✓ print_data_ready signal: {filename}, {len(data)} bytes")

        # Example custom handling: offer to save the print data
        reply = QMessageBox.question(
            self,
            "Custom Print Handler",
            f"Print data ready for: {filename}\n"
            f"Size: {len(data)} bytes\n\n"
            "Would you like to save this to a file instead of printing?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Print Data",
                filename,
                "PDF Files (*.pdf);;All Files (*)"
            )

            if save_path:
                try:
                    with open(save_path, 'wb') as f:
                        f.write(data)
                    self._log(f"✓ Print data saved to: {save_path}")
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Print data saved to:\n{save_path}"
                    )
                except Exception as e:
                    self._log(f"Error saving print data: {e}")
                    QMessageBox.critical(
                        self,
                        "Save Error",
                        f"Failed to save print data:\n{e}"
                    )
        else:
            self._log("Custom print handler: user declined to save")

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
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    window = PrintHandlersWindow()
    window.show()

    # Show info dialog
    QMessageBox.information(
        window,
        "Print Handlers Demo",
        "<h3>Print Handler Options</h3>"
        "<p><b>SYSTEM:</b> Opens PDF in your system's default PDF viewer. "
        "Simple and reliable, works everywhere.</p>"

        "<p><b>QT_DIALOG:</b> Shows Qt's native print dialog with page selection, "
        "preview, and printer settings. Requires pypdfium2 to be installed.</p>"

        "<p><b>EMIT_SIGNAL:</b> Emits a signal with the PDF data instead of printing. "
        "This allows your application to implement custom print workflows.</p>"

        "<p><i>Load a PDF and try each handler to see how they work!</i></p>"
    )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
