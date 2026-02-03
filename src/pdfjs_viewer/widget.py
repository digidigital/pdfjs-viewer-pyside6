"""Main PDF viewer widget - thin wrapper delegating to backend."""

from pathlib import Path
from typing import Optional, Union

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .backend_inprocess import InProcessBackend
from .config import ConfigPresets, PDFViewerConfig


class PDFViewerWidget(QWidget):
    """Qt widget for viewing and annotating PDF files using PDF.js.

    This widget embeds a QWebEngineView running PDF.js with full support for:
    - PDF viewing and navigation
    - Annotations (highlight, text, ink, stamps, signatures)
    - Saving PDFs with annotations
    - Printing with annotations
    - Light/dark theme support with automatic synchronization
    - Configurable feature control and security settings

    Signals:
        pdf_loaded: Emitted when PDF is successfully loaded (metadata: dict)
        pdf_saved: Emitted when PDF is saved (data: bytes, path: str)
        print_requested: Emitted when print is triggered (data: bytes) - for SYSTEM/QT_DIALOG handlers
        print_data_ready: Emitted for EMIT_SIGNAL handler (data: bytes, filename: str)
        annotation_modified: Emitted when annotations are modified
        page_changed: Emitted when page changes (current: int, total: int)
        error_occurred: Emitted on errors (message: str)
        external_link_blocked: Emitted when external link is blocked (url: str)
    """

    # Signals
    pdf_loaded = Signal(dict)
    pdf_saved = Signal(bytes, str)
    print_requested = Signal(bytes)
    print_data_ready = Signal(bytes, str)  # (pdf_data, original_filename)
    annotation_modified = Signal()
    page_changed = Signal(int, int)
    error_occurred = Signal(str)
    external_link_blocked = Signal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        config: Optional[PDFViewerConfig] = None,
        preset: Optional[str] = None,
        customize: Optional[dict] = None,
        pdfjs_path: Optional[str] = None
    ):
        """Initialize PDF viewer widget.

        Args:
            parent: Parent Qt widget
            config: Full configuration object (takes precedence over preset)
            preset: Preset name ("readonly", "simple", "annotation", "form",
                   "kiosk", "presentation", "safer", "unrestricted")
            customize: Dict of overrides for preset (requires preset parameter)
            pdfjs_path: Path to custom PDF.js installation (optional)

        Configuration Priority (highest to lowest):
            1. config parameter (if provided, preset/customize ignored)
            2. preset + customize
            3. annotation preset (default)

        Examples:
            Simple preset usage:
            >>> viewer = PDFViewerWidget(preset="readonly")

            Customize a preset:
            >>> viewer = PDFViewerWidget(
            ...     preset="readonly",
            ...     customize={"features": {"save_enabled": True}}
            ... )

            Full control (advanced):
            >>> config = PDFViewerConfig(...)
            >>> viewer = PDFViewerWidget(config=config)

            Hybrid approach:
            >>> config = ConfigPresets.readonly()
            >>> config.features.save_enabled = True
            >>> viewer = PDFViewerWidget(config=config)

        Raises:
            ValueError: If preset name is unknown or customize used without preset
        """
        super().__init__(parent)

        # Resolve configuration
        if config is None:
            if customize and not preset:
                raise ValueError(
                    "customize parameter requires preset parameter. "
                    "Use: PDFViewerWidget(preset='name', customize={...})"
                )

            if preset is not None:
                if customize:
                    config = ConfigPresets.custom(base=preset, **customize)
                else:
                    config = ConfigPresets.get(preset)
            else:
                # Default: annotation preset
                config = ConfigPresets.annotation()

        # Create in-process backend
        self.backend = InProcessBackend(self)

        # Initialize backend
        self.backend.initialize(config, pdfjs_path)

        # Connect all backend signals to widget signals
        self.backend.pdf_loaded.connect(self.pdf_loaded.emit)
        self.backend.save_requested.connect(self.pdf_saved.emit)
        self.backend.print_requested.connect(self.print_requested.emit)
        self.backend.print_data_ready.connect(self.print_data_ready.emit)
        self.backend.annotation_modified.connect(self.annotation_modified.emit)
        self.backend.page_changed.connect(self.page_changed.emit)
        self.backend.error_occurred.connect(self.error_occurred.emit)
        self.backend.external_link_blocked.connect(self.external_link_blocked.emit)

        # Create layout and add backend widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.backend.get_widget())

    def load_pdf(
        self,
        source: Union[str, Path, bytes],
        page: Optional[int] = None,
        zoom: Optional[Union[str, int, float]] = None,
        pagemode: Optional[str] = None,
        nameddest: Optional[str] = None
    ):
        """Load a PDF from file path or bytes with optional viewer options.

        Args:
            source: PDF file path (str or Path) or PDF data as bytes
            page: Page number to open (1-indexed, e.g., page=1 opens first page)
            zoom: Zoom level - named modes ('page-width', 'page-height', 'page-fit', 'auto')
                  or numeric percentage (10-1000, e.g., 150 for 150%)
            pagemode: Sidebar state - 'none', 'thumbs', 'bookmarks', or 'attachments'
            nameddest: Named destination to navigate to (PDF internal destination)

        Raises:
            FileNotFoundError: If file path doesn't exist.
            PermissionError: If file cannot be read.
            ValueError: If source type or parameters are invalid.

        Examples:
            Load PDF and open at page 5:
            >>> viewer.load_pdf("document.pdf", page=5, zoom="page-width")

            Load PDF with bookmarks sidebar:
            >>> viewer.load_pdf("document.pdf", pagemode="bookmarks")

            Load PDF bytes at specific page:
            >>> with open("doc.pdf", "rb") as f:
            ...     viewer.load_pdf(f.read(), page=3, zoom=150)
        """
        if isinstance(source, bytes):
            self.backend.load_pdf_bytes(
                source,
                page=page,
                zoom=zoom,
                pagemode=pagemode,
                nameddest=nameddest
            )
        elif isinstance(source, (str, Path)):
            self.backend.load_pdf(
                str(Path(source)),
                page=page,
                zoom=zoom,
                pagemode=pagemode,
                nameddest=nameddest
            )
        else:
            raise ValueError(f"Invalid source type: {type(source)}")

    def load_pdf_bytes(
        self,
        data: bytes,
        filename: str = "document.pdf",
        page: Optional[int] = None,
        zoom: Optional[Union[str, int, float]] = None,
        pagemode: Optional[str] = None,
        nameddest: Optional[str] = None
    ):
        """Load a PDF from bytes with optional viewer options.

        Args:
            data: PDF file data as bytes
            filename: Name to display for the document
            page: Page number to open (1-indexed)
            zoom: Zoom level - named modes ('page-width', 'page-height', 'page-fit', 'auto')
                  or numeric percentage (10-1000, e.g., 150 for 150%)
            pagemode: Sidebar state - 'none', 'thumbs', 'bookmarks', or 'attachments'
            nameddest: Named destination to navigate to

        Raises:
            ValueError: If parameters are invalid

        Examples:
            Load PDF bytes and open at page 3:
            >>> with open("doc.pdf", "rb") as f:
            ...     viewer.load_pdf_bytes(f.read(), page=3, zoom="page-fit")
        """
        self.backend.load_pdf_bytes(
            data,
            filename,
            page=page,
            zoom=zoom,
            pagemode=pagemode,
            nameddest=nameddest
        )

    def show_blank_page(self):
        """Show blank viewer with no PDF loaded.

        The viewer will display in the current theme (light/dark mode).
        """
        self.backend.show_blank_page()

    def print_pdf(self):
        """Trigger print for current PDF.

        This is a convenience method that triggers the JavaScript print action.
        The actual printing is handled by the configured print handler.
        """
        self.backend.print_pdf()

    def save_pdf(self, output_path: Optional[str] = None) -> Optional[bytes]:
        """Save current PDF with annotations.

        If output_path is provided, saves to that path.
        Otherwise, triggers the save dialog.

        Args:
            output_path: Optional output file path.

        Returns:
            PDF data as bytes if successful, None otherwise.
        """
        self.backend.save_pdf()
        return None

    def has_annotations(self) -> bool:
        """Check if current PDF has annotations.

        Returns:
            True if PDF has been annotated, False otherwise.
        """
        return self.backend.has_annotations()

    def get_page_count(self) -> int:
        """Get total number of pages.

        Returns:
            Total page count, or 0 if no PDF loaded.
        """
        return self.backend.get_page_count()

    def get_current_page(self) -> int:
        """Get current page number.

        Returns:
            Current page number (1-indexed), or 0 if no PDF loaded.
        """
        return self.backend.get_current_page()

    def goto_page(self, page: int):
        """Navigate to specific page.

        Args:
            page: Page number to navigate to (1-indexed).
        """
        self.backend.goto_page(page)

    def set_pdfjs_path(self, path: str):
        """Set custom PDF.js path and reload viewer.

        Args:
            path: Path to PDF.js distribution directory.

        Raises:
            ValueError: If path is invalid.
        """
        # Reinitialize backend with new path
        config = self.backend.config
        self.backend.cleanup()
        self.backend = InProcessBackend(self)
        self.backend.initialize(config, path)

        # Reconnect signals
        self.backend.pdf_loaded.connect(self.pdf_loaded.emit)
        self.backend.save_requested.connect(self.pdf_saved.emit)
        self.backend.print_requested.connect(self.print_requested.emit)
        self.backend.print_data_ready.connect(self.print_data_ready.emit)
        self.backend.annotation_modified.connect(self.annotation_modified.emit)
        self.backend.page_changed.connect(self.page_changed.emit)
        self.backend.error_occurred.connect(self.error_occurred.emit)
        self.backend.external_link_blocked.connect(self.external_link_blocked.emit)

        # Update layout
        layout = self.layout()
        # Remove old widget
        old_widget = layout.takeAt(0).widget()
        if old_widget:
            old_widget.deleteLater()
        # Add new widget
        layout.addWidget(self.backend.get_widget())

    def get_pdfjs_version(self) -> str:
        """Get bundled PDF.js version.

        Returns:
            Version string (e.g., "5.4.530").
        """
        return self.backend.resource_manager.get_pdfjs_version()

    def has_unsaved_changes(self) -> bool:
        """Check if document has unsaved annotations.

        This checks PDF.js's internal modification tracking, which is:
        - Set to true when annotations are modified
        - Reset to false after saveDocument() completes

        Returns:
            True if there are unsaved changes, False otherwise.

        Example:
            >>> if viewer.has_unsaved_changes():
            ...     print("Document has unsaved annotations")
        """
        return self.backend.has_unsaved_changes()

    def handle_unsaved_changes(self) -> bool:
        """Handle unsaved changes according to config.

        Based on the unsaved_changes_action configuration:
        - "disabled": Returns True immediately (no prompt)
        - "prompt": Shows dialog with Save As / Save / Discard options
        - "auto_save": Automatically saves to original file

        The save operation is asynchronous: if a save is needed, this method
        triggers PDFViewerApplication.download() in JavaScript and returns
        False. The actual file write happens when the data arrives via the
        bridge's save_requested signal. After saving, the deferred action
        (close, load) is executed automatically.

        Returns:
            True if safe to proceed immediately (no changes, discarded, disabled).
            False if async save was triggered or Save As was cancelled — caller
            should NOT proceed (e.g., ignore the close event).

        Example:
            >>> # In closeEvent:
            >>> if not viewer.handle_unsaved_changes():
            ...     event.ignore()  # Save in progress or cancelled
            ...     return
        """
        return self.backend.handle_unsaved_changes()

    def closeEvent(self, event):
        """Handle widget close event.

        If unsaved_changes_action is configured, checks for unsaved annotations
        and prompts the user before closing.

        When an async save is triggered, this method ignores the close event.
        After the save completes, the backend re-triggers close automatically,
        and on the second call has_unsaved_changes() returns False, allowing
        the close to proceed.

        Args:
            event: Close event.
        """
        # Handle unsaved changes before closing
        # Returns False if async save was triggered or Save As cancelled
        if not self.backend.handle_unsaved_changes():
            event.ignore()
            return

        # Use enhanced shutdown sequence if available
        if hasattr(self.backend, '_cleanup_before_shutdown'):
            self.backend._cleanup_before_shutdown()
        else:
            self.backend.cleanup()
        super().closeEvent(event)
