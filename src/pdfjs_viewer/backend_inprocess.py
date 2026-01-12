"""In-process backend using QWebEngineView.

This backend runs PDF.js in a QWebEngineView within the main process.
It provides full functionality but shares the main process memory space.
"""

import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Optional, Union

from PySide6.QtCore import QUrl, QUrlQuery
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QProgressDialog, QMessageBox, QFileDialog

from .viewer_backend import ViewerBackend, register_backend
from .bridge import PDFJavaScriptBridge
from .config import PDFViewerConfig, PrintHandler
from .print_utils import get_temp_file_manager, PrintWorker
from .print_manager import PrintManager
from .resources import PDFResourceManager
from .security import PDFSecurityManager
from .ui_translations import get_translations
from .print_translations import get_translation


class CustomWebEngineView(QWebEngineView):
    """Custom QWebEngineView - currently just a placeholder for future customizations."""

    def __init__(self, disable_context_menu: bool = True, parent=None):
        """Initialize custom web engine view.

        Args:
            disable_context_menu: If True, disable the native context menu (handled by JS).
            parent: Parent widget.
        """
        super().__init__(parent)
        self._disable_context_menu = disable_context_menu

    # Context menu is handled by custom JavaScript module (context_menu.js)
    # to enable proper event propagation and custom menu features


class InProcessBackend(ViewerBackend):
    """In-process backend implementation using QWebEngineView.

    This backend runs PDF.js in a QWebEngineView within the main Qt application process.
    It provides full functionality with direct access to the WebEngine instance.

    The backend handles:
    - PDF loading from files or bytes
    - WebEngine setup and configuration
    - JavaScript bridge communication
    - Print handling (system, Qt dialog, or signal emission)
    - Theme management
    - Annotation tracking
    """

    def __init__(self, parent=None):
        """Initialize the in-process backend.

        Args:
            parent: Parent QObject (usually the PDFViewerWidget)
        """
        super().__init__(parent)

        # State variables
        self.config: Optional[PDFViewerConfig] = None
        self.resource_manager: Optional[PDFResourceManager] = None
        self.security_manager: Optional[PDFSecurityManager] = None
        self.web_view: Optional[CustomWebEngineView] = None
        self.bridge: Optional[PDFJavaScriptBridge] = None
        self.channel: Optional[QWebChannel] = None
        self.tr = None
        self._page: Optional['PDFWebEnginePage'] = None  # Track page for proper cleanup
        self._profile: Optional['QWebEngineProfile'] = None  # Track profile for proper cleanup

        self._current_pdf_url: Optional[str] = None
        self._current_pdf_directory: Optional[str] = None  # Directory of loaded PDF
        self._has_annotations = False
        self._last_print_data: Optional[bytes] = None

        # Temporary file management for performance
        self._temp_pdf_path: Optional[Path] = None  # Temp copy of PDF
        self._original_pdf_path: Optional[Path] = None  # Original PDF location

        # Print manager for separate process printing
        self._print_manager: Optional[PrintManager] = None

        # Track state for crash recovery (page position, metadata, recovery flag)
        self._current_page: int = 1
        self._total_pages: int = 0
        self._pdf_metadata: Optional[dict] = None
        self._is_recovering_from_crash: bool = False

    def initialize(self, config: PDFViewerConfig, pdfjs_path: Optional[str] = None):
        """Initialize the backend with configuration.

        Args:
            config: PDFViewerConfig instance
            pdfjs_path: Optional custom path to PDF.js installation
        """
        self.config = config

        # Initialize managers
        self.resource_manager = PDFResourceManager(pdfjs_path)
        self.security_manager = PDFSecurityManager(self.config.security)

        # Load UI translations
        self.tr = get_translations()

        # Create web view
        self._setup_web_view()

        # Setup bridge
        self._setup_bridge()

        # Load viewer
        self._load_viewer()

    def _setup_web_view(self):
        """Setup the QWebEngineView with stability configuration."""
        from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
        import uuid

        # Apply safer_mode preset if enabled
        stability = self.config.stability
        if stability.safer_mode:
            # Override with safe defaults
            stability.use_isolated_profile = True
            stability.disable_webgl = True
            stability.disable_gpu = True
            stability.disable_cache = True
            stability.disable_local_storage = True
            stability.disable_service_workers = True

        # Create or get profile
        if stability.use_isolated_profile:
            # Create isolated profile with unique name
            profile_name = stability.profile_name or f"pdfjs_viewer_{uuid.uuid4().hex[:8]}"
            profile = QWebEngineProfile(profile_name, self.parent())

            # Configure profile cache
            if stability.disable_cache:
                profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
            if stability.max_cache_size_mb > 0:
                profile.setHttpCacheMaximumSize(stability.max_cache_size_mb * 1024 * 1024)

            # Configure persistent data
            if stability.disable_local_storage or stability.disable_session_storage or stability.disable_databases:
                profile.setPersistentStoragePath("")  # Disable persistent storage
        else:
            # Use default profile
            profile = QWebEngineProfile.defaultProfile()

        # Create secure page with profile
        secure_page = self.security_manager.create_page(profile=profile, parent=self.parent())

        # Store references for proper cleanup
        self._page = secure_page
        self._profile = profile

        # Configure WebEngine settings for stability
        settings = secure_page.settings()

        # Disable crash-prone features
        if stability.disable_webgl:
            settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, False)
            settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, False)

        if stability.disable_local_storage:
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, False)

        # Additional stability settings
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadIconsForPage, False)

        # Create web view
        self.web_view = CustomWebEngineView(
            disable_context_menu=self.config.disable_context_menu,
            parent=self.parent()
        )
        self.web_view.setPage(secure_page)

        # Connect to crash detection for automatic recovery
        secure_page.renderProcessTerminated.connect(self._on_render_process_terminated)

    def _setup_bridge(self):
        """Setup QWebChannel bridge for JavaScript-Python communication."""
        self.bridge = PDFJavaScriptBridge(self.parent())

        # Connect bridge signals to backend signals
        self.bridge.save_requested.connect(self._on_save_requested)
        self.bridge.print_requested.connect(self._on_print_requested)
        self.bridge.load_requested.connect(self._on_load_requested)
        self.bridge.pdf_loaded.connect(self._on_pdf_loaded)
        self.bridge.annotation_changed.connect(self._on_annotation_changed)
        self.bridge.page_changed.connect(self._on_page_changed)
        self.bridge.error_occurred.connect(self._on_error_occurred)
        self.bridge.text_copied.connect(self._on_text_copied)

        # Setup web channel
        self.channel = QWebChannel(self.web_view.page())
        self.channel.registerObject('pdfBridge', self.bridge)
        self.web_view.page().setWebChannel(self.channel)

    def _load_viewer(self):
        """Load the PDF.js viewer HTML."""
        viewer_url = self.resource_manager.get_viewer_url()
        self.web_view.setUrl(viewer_url)

        # Inject scripts after page loads
        self.web_view.loadFinished.connect(self._on_page_loaded)

    def _on_page_loaded(self, ok: bool):
        """Called when viewer page finishes loading.

        Args:
            ok: True if page loaded successfully.
        """
        if not ok:
            self.error_occurred.emit("Failed to load PDF.js viewer")
            return

        # First, inject Qt's qwebchannel.js
        try:
            from PySide6.QtCore import QFile, QIODevice
            qwebchannel_file = QFile(":/qtwebchannel/qwebchannel.js")
            if qwebchannel_file.open(QIODevice.OpenModeFlag.ReadOnly):
                qwebchannel_js = bytes(qwebchannel_file.readAll()).decode('utf-8')
                qwebchannel_file.close()
                self.web_view.page().runJavaScript(qwebchannel_js)
            else:
                pass
        except Exception as e:
            pass

        # Inject bridge script
        try:
            bridge_js = self.resource_manager.load_template('bridge.js')
            self.web_view.page().runJavaScript(bridge_js, self._handle_js_result)
        except Exception as e:
            self.error_occurred.emit(f"Failed to load bridge: {e}")
            return  # Critical failure, don't continue

        # Inject interceptor script
        try:
            interceptor_js = self.resource_manager.load_template('interceptor.js')
            self.web_view.page().runJavaScript(interceptor_js, self._handle_js_result)
        except Exception as e:
            self.error_occurred.emit(f"Failed to load interceptor: {e}")
            # Non-critical, continue

        # Dialog safety injection skipped: performance optimization
        # (Previous implementation did not reduce crashes and caused console overhead)

        # Inject feature control script
        try:
            feature_config = self.config.features.to_js_config()
            feature_config_js = f"window.pdfjsFeatureConfig = {json.dumps(feature_config)};"
            self.web_view.page().runJavaScript(feature_config_js)

            feature_control_js = self.resource_manager.load_template('feature_control.js')
            self.web_view.page().runJavaScript(feature_control_js, self._handle_js_result)
        except Exception as e:
            self.error_occurred.emit(f"Failed to load feature control: {e}")
            # Non-critical, continue

        # Inject custom context menu handler (if context menu is disabled)
        if self.config.disable_context_menu:
            try:
                context_menu_js = self.resource_manager.load_template('context_menu.js')
                self.web_view.page().runJavaScript(context_menu_js, self._handle_js_result)
            except Exception as e:
                self.error_occurred.emit(f"Failed to load context menu handler: {e}")
                # Non-critical, continue

        # Theme is handled automatically by QtWebEngine's prefers-color-scheme
        # PDF.js has built-in dark mode CSS that responds to system theme
        # No custom theme.js injection needed

    def _handle_js_result(self, result):
        """Handle JavaScript execution results.

        Args:
            result: Result from JavaScript execution (or error).
        """
        # Log JavaScript errors if any
        if isinstance(result, str) and ('error' in result.lower() or 'exception' in result.lower()):
            self.error_occurred.emit(f"JavaScript error: {result}")

    def _cleanup_temp_pdf(self):
        """Clean up temporary PDF file if it exists."""
        if self._temp_pdf_path and self._temp_pdf_path.exists():
            try:
                self._temp_pdf_path.unlink()
            except Exception:
                pass  # Ignore cleanup errors
            finally:
                self._temp_pdf_path = None

    def _create_temp_pdf_copy(self, source_path: Path) -> Path:
        """Create a temporary copy of the PDF file.

        This improves performance when loading from network locations
        and provides crash isolation.

        Args:
            source_path: Original PDF file path

        Returns:
            Path to temporary PDF copy

        Raises:
            IOError: If copy fails
        """
        import tempfile
        import shutil

        # Clean up any existing temp file
        self._cleanup_temp_pdf()

        # Create temp file with same extension
        temp_dir = Path(tempfile.gettempdir()) / "pdfjs_viewer_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Use unique filename to avoid conflicts
        import uuid
        temp_filename = f"pdf_{uuid.uuid4().hex[:8]}.pdf"
        temp_path = temp_dir / temp_filename

        try:
            # Copy file to temp location
            shutil.copy2(source_path, temp_path)
            return temp_path
        except Exception as e:
            # Clean up on failure
            if temp_path.exists():
                temp_path.unlink()
            raise IOError(f"Failed to create temp PDF copy: {e}")

    def _build_viewer_url(
        self,
        pdf_url: QUrl,
        page: Optional[int] = None,
        zoom: Optional[Union[str, int, float]] = None,
        pagemode: Optional[str] = None,
        nameddest: Optional[str] = None
    ) -> QUrl:
        """Build viewer URL with PDF file and optional viewer options.

        Args:
            pdf_url: QUrl pointing to the PDF file
            page: Page number to open (1-indexed)
            zoom: Zoom level - named ('page-width', 'page-height', 'page-fit', 'auto')
                  or numeric (percentage as int/float, e.g., 150 for 150%)
            pagemode: Sidebar state - 'none', 'thumbs', 'bookmarks', or 'attachments'
            nameddest: Named destination to navigate to

        Returns:
            QUrl with viewer URL and query parameters

        Raises:
            ValueError: If parameters are invalid
        """
        # Validate parameters
        if page is not None and page < 1:
            raise ValueError(f"Page number must be >= 1, got {page}")

        if zoom is not None:
            valid_zoom_modes = {'page-width', 'page-height', 'page-fit', 'auto'}
            if isinstance(zoom, str):
                if zoom not in valid_zoom_modes:
                    raise ValueError(
                        f"Invalid zoom mode '{zoom}'. Valid modes: {', '.join(valid_zoom_modes)}"
                    )
            elif isinstance(zoom, (int, float)):
                if not (10 <= zoom <= 1000):
                    raise ValueError(f"Zoom percentage must be between 10 and 1000, got {zoom}")
            else:
                raise ValueError(f"zoom must be str or number, got {type(zoom)}")

        if pagemode is not None:
            valid_pagemodes = {'none', 'thumbs', 'bookmarks', 'attachments'}
            if pagemode not in valid_pagemodes:
                raise ValueError(
                    f"Invalid pagemode '{pagemode}'. Valid modes: {', '.join(valid_pagemodes)}"
                )

        # Build query using QUrlQuery for proper encoding
        query = QUrlQuery()
        query.addQueryItem('file', pdf_url.toString())
        
        fragments = []
        
        if page is not None:
            fragments.append(f'page={str(page)}')

        if zoom is not None:
            fragments.append(f'zoom={str(zoom)}')

        if pagemode is not None:
            fragments.append(f'pagemode={str(pagemode)}')
 
        if nameddest is not None:
            fragments.append(f'nameddest={str(nameddest)}')

        # Build final viewer URL
        viewer_url = self.resource_manager.get_viewer_url()
        viewer_qurl = QUrl(viewer_url)
        viewer_qurl.setQuery(query)
        if fragments:
            viewer_qurl.setFragment("&".join(fragments))
        return viewer_qurl

    def load_pdf(
        self,
        file_path: str,
        page: Optional[int] = None,
        zoom: Optional[Union[str, int, float]] = None,
        pagemode: Optional[str] = None,
        nameddest: Optional[str] = None
    ):
        """Load a PDF file with optional viewer options.

        For performance and compatibility (especially with network locations),
        the PDF is copied to a temporary directory before loading.

        Uses the standard PDF.js approach: reload viewer.html with query parameters.
        This is more reliable than JavaScript injection.

        Args:
            file_path: Absolute path to the PDF file
            page: Page number to open (1-indexed, e.g., page=1 opens first page)
            zoom: Zoom level - named modes ('page-width', 'page-height', 'page-fit', 'auto')
                  or numeric percentage (10-1000, e.g., 150 for 150%)
            pagemode: Sidebar state - 'none', 'thumbs', 'bookmarks', or 'attachments'
            nameddest: Named destination to navigate to (PDF internal destination)

        Raises:
            FileNotFoundError: If file doesn't exist.
            PermissionError: If file cannot be read.
            ValueError: If file is not a valid PDF or parameters are invalid.
            IOError: If temp copy fails.

        Examples:
            Open PDF at page 5 with page-width zoom:
            >>> backend.load_pdf("document.pdf", page=5, zoom="page-width")

            Open PDF with bookmarks sidebar visible:
            >>> backend.load_pdf("document.pdf", pagemode="bookmarks")

            Open PDF at 150% zoom:
            >>> backend.load_pdf("document.pdf", zoom=150)
        """
        from .config import validate_pdf_file

        path = Path(file_path)

        # Handle UNC paths on Windows
        if str(path).startswith('\\\\'):
            # UNC path - convert to Path for validation
            path = Path(str(path))

        path = path.absolute()

        # Validate source file exists
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        if not os.access(path, os.R_OK):
            raise PermissionError(f"Cannot read PDF: {path}")

        # Validate it's actually a PDF file (check magic bytes)
        if not validate_pdf_file(str(path)):
            raise ValueError(
                f"File is not a valid PDF (missing %PDF header): {path}"
            )

        # Store original path for save dialog
        self._original_pdf_path = path
        self._current_pdf_directory = str(path.parent)

        # Create temporary copy for better performance and compatibility
        try:
            temp_path = self._create_temp_pdf_copy(path)
            self._temp_pdf_path = temp_path

            # Use temp location
            pdf_url = QUrl.fromLocalFile(str(temp_path))
        except IOError:
            # Fall back to direct loading if temp copy fails
            pdf_url = QUrl.fromLocalFile(str(path))

        self._current_pdf_url = pdf_url.toString()
        self._has_annotations = False

        # Build viewer URL with PDF file and optional viewer options
        viewer_qurl = self._build_viewer_url(
            pdf_url,
            page=page,
            zoom=zoom,
            pagemode=pagemode,
            nameddest=nameddest
        )

        # Reload the viewer with the new PDF
        self.web_view.setUrl(viewer_qurl)

    def load_pdf_bytes(
        self,
        pdf_data: bytes,
        filename: str = "document.pdf",
        page: Optional[int] = None,
        zoom: Optional[Union[str, int, float]] = None,
        pagemode: Optional[str] = None,
        nameddest: Optional[str] = None
    ):
        """Load a PDF from bytes with optional viewer options.

        Creates a temporary file and loads it using the standard URL parameter approach.

        Args:
            pdf_data: PDF file contents as bytes
            filename: Name to display for the document (stored for save dialog)
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
            ...     backend.load_pdf_bytes(f.read(), page=3, zoom="page-fit")
        """
        import tempfile
        import uuid

        # Clean up any previous temp file
        self._cleanup_temp_pdf()

        # Create temp file for the PDF bytes
        temp_dir = Path(tempfile.gettempdir()) / "pdfjs_viewer_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Use unique filename
        temp_filename = f"pdf_{uuid.uuid4().hex[:8]}.pdf"
        temp_path = temp_dir / temp_filename

        try:
            # Write bytes to temp file
            with open(temp_path, 'wb') as f:
                f.write(pdf_data)

            self._temp_pdf_path = temp_path

            # No original path for bytes, but store filename for display
            self._original_pdf_path = None
            self._current_pdf_directory = None

            # Create file URL
            pdf_url = QUrl.fromLocalFile(str(temp_path))
            self._current_pdf_url = pdf_url.toString()
            self._has_annotations = False

            # Build viewer URL with PDF file and optional viewer options
            viewer_qurl = self._build_viewer_url(
                pdf_url,
                page=page,
                zoom=zoom,
                pagemode=pagemode,
                nameddest=nameddest
            )

            # Reload the viewer with the PDF
            self.web_view.setUrl(viewer_qurl)

        except Exception as e:
            # Clean up on failure
            if temp_path.exists():
                temp_path.unlink()
            raise IOError(f"Failed to load PDF from bytes: {e}")

    def show_blank_page(self):
        """Show blank viewer with no PDF loaded."""
        # Clean up temp file when closing PDF
        self._cleanup_temp_pdf()

        self._current_pdf_url = None
        self._has_annotations = False
        self._original_pdf_path = None
        self._current_pdf_directory = None

        # Reload viewer with empty file parameter to prevent demo PDF from loading
        # PDF.js loads "compressed.tracemonkey-pldi-09.pdf" by default if no file param
        viewer_url = self.resource_manager.get_viewer_url()
        query = QUrlQuery()
        query.addQueryItem('file', '')  # Empty file parameter prevents default PDF
        viewer_qurl = QUrl(viewer_url)
        viewer_qurl.setQuery(query)
        self.web_view.setUrl(viewer_qurl)

    def print_pdf(self):
        """Trigger print for current PDF."""
        # Trigger JavaScript print by simulating print button click
        # The interceptor.js will catch this and call bridge.print_pdf()
        js_code = '''
        (function() {
            const printButton = document.getElementById('printButton');
            if (printButton) {
                printButton.click();
            } else {
                console.error('Print button not found');
            }
        })();
        '''
        self.web_view.page().runJavaScript(js_code)

    def save_pdf(self):
        """Save the current PDF with annotations."""
        # Trigger JavaScript save
        # The actual save is handled by the bridge callback
        js_code = 'PDFViewerApplication.download();'
        self.web_view.page().runJavaScript(js_code)

    def get_widget(self):
        """Get the Qt widget to display.

        Returns:
            QWidget: The QWebEngineView widget
        """
        return self.web_view

    def cleanup(self):
        """Clean up resources before destruction.

        IMPORTANT: Clean up order matters! Page must be deleted before profile
        to avoid Qt warning: "Release of profile requested but WebEnginePage still not deleted"
        """
        # Clean up temporary PDF file
        self._cleanup_temp_pdf()

        if self.web_view:
            # Stop loading
            self.web_view.stop()

            # Clear page from view first
            self.web_view.setPage(None)

            # Disconnect signals
            try:
                self.web_view.loadFinished.disconnect()
            except:
                pass

        # Delete page BEFORE profile (critical for proper cleanup)
        if self._page:
            try:
                self._page.deleteLater()
            except:
                pass
            self._page = None

        # Delete profile after page
        if self._profile:
            try:
                # Only delete if it's not the default profile
                from PySide6.QtWebEngineCore import QWebEngineProfile
                if self._profile != QWebEngineProfile.defaultProfile():
                    self._profile.deleteLater()
            except:
                pass
            self._profile = None

        if self.bridge:
            self.bridge.deleteLater()
            self.bridge = None

        if self.channel:
            self.channel.deleteLater()
            self.channel = None

    def __del__(self):
        """Destructor - ensure temp files are cleaned up even on garbage collection."""
        try:
            self._cleanup_temp_pdf()
        except:
            # Ignore errors during garbage collection
            pass

    def has_annotations(self) -> bool:
        """Check if current PDF has annotations.

        Returns:
            True if PDF has been annotated, False otherwise.
        """
        return self._has_annotations

    def get_page_count(self) -> int:
        """Get total number of pages.

        Returns:
            Total page count, or 0 if no PDF loaded.
        """
        # This would need to be queried via JavaScript and stored
        # For now, return 0 as placeholder
        return 0

    def get_current_page(self) -> int:
        """Get current page number.

        Returns:
            Current page number (1-indexed), or 0 if no PDF loaded.
        """
        # This would need to be queried via JavaScript and stored
        # For now, return 0 as placeholder
        return 0

    def goto_page(self, page: int):
        """Navigate to specific page.

        Args:
            page: Page number to navigate to (1-indexed).
        """
        js_code = f'PDFViewerApplication.page = {page};'
        self.web_view.page().runJavaScript(js_code)

    def _get_page_count_from_data(self, data: bytes) -> int:
        """Get page count from PDF data.

        Args:
            data: PDF data as bytes.

        Returns:
            Number of pages, or 1 if unable to determine.
        """
        try:
            import pypdfium2 as pdfium
            import io
            pdf = pdfium.PdfDocument(io.BytesIO(data))
            count = len(pdf)
            pdf.close()
            return count
        except Exception:
            # Fallback: try pikepdf
            try:
                import pikepdf
                import io
                pdf = pikepdf.open(io.BytesIO(data))
                count = len(pdf.pages)
                pdf.close()
                return count
            except Exception:
                # Can't determine page count, return 1
                return 1

    def _print_with_system_handler(self, data: bytes, filename: str):
        """Print using system default PDF viewer (SYSTEM handler).

        Args:
            data: PDF data to print.
            filename: Original filename for temp file.
        """
        try:
            # Create temp file with original filename
            temp_file_manager = get_temp_file_manager()
            temp_path = temp_file_manager.create_temp_pdf(data, filename)

            # Open with system's default PDF viewer
            system = platform.system()

            if system == 'Linux':
                subprocess.Popen(['xdg-open', str(temp_path)])
            elif system == 'Darwin':  # macOS
                subprocess.Popen(['open', str(temp_path)])
            elif system == 'Windows':
                os.startfile(str(temp_path))

        except Exception as e:
            self.error_occurred.emit(f"System print error: {e}")

    def _print_with_qt_dialog(self, data: bytes):
        """Print using custom print dialog in separate process (QT_DIALOG handler).

        This uses a separate process to show the print dialog, providing crash isolation
        from the main WebEngine process and preventing Speicherzugriffsfehler.

        Args:
            data: PDF data to print.
        """
        try:
            # Get page count from PDF
            total_pages = self._get_page_count_from_data(data)

            # Create print manager if not exists
            if self._print_manager is None:
                self._print_manager = PrintManager(self)
                self._print_manager.print_completed.connect(self._on_process_print_completed)
                self._print_manager.error_occurred.connect(self._on_process_print_error)

            # Check if already printing
            if self._print_manager.is_running():
                tr = get_translation()
                QMessageBox.warning(
                    self.parent(),
                    tr['print_in_progress'],
                    tr['print_already_running']
                )
                return

            # Show print dialog and print in separate process
            # This is fire-and-forget - no blocking dialogs on completion
            # Status message shown in print process itself
            self._print_manager.show_print_dialog_and_print(
                pdf_data=data,
                total_pages=total_pages,
                timeout_ms=300000  # 5 minute timeout
            )

        except Exception as e:
            self.error_occurred.emit(f"Print process error: {e}")

    def _print_with_signal_emission(self, data: bytes, filename: str):
        """Print by emitting signal with PDF data (EMIT_SIGNAL handler).

        Args:
            data: PDF data to print.
            filename: Original filename.
        """
        # Emit signal for application to handle
        self.print_data_ready.emit(data, filename)

    def _on_process_print_completed(self, success: bool, message: str):
        """Handle print completion from separate process.

        Fire-and-forget pattern: no blocking dialogs, just emit signals for logging.

        Args:
            success: Whether printing succeeded
            message: Status message
        """
        # Fire-and-forget: silently complete, only log errors for debugging
        if not success and message and "cancelled" not in message.lower():
            # Only emit error signal for logging, no blocking dialog
            self.error_occurred.emit(f"Print completed with warning: {message}")
        # Success or cancellation - no user notification needed

    def _on_process_print_error(self, error_msg: str):
        """Handle print error from separate process.

        Fire-and-forget pattern: only emit error signal for logging, no blocking dialog.

        Args:
            error_msg: Error message
        """
        # Only emit error signal for logging/console output, no blocking dialog
        self.error_occurred.emit(f"Print error: {error_msg}")

    # Signal handlers - connect bridge signals to backend signals
    def _on_save_requested(self, data: bytes, filename: str):
        """Handle save request from bridge.

        Args:
            data: PDF data with annotations.
            filename: Suggested filename.
        """
        # Use original PDF path if available, otherwise construct from directory + filename
        if self._original_pdf_path and self._original_pdf_path.exists():
            # Use original path as default (user can change the name if they want)
            initial_path = str(self._original_pdf_path)
        elif self._current_pdf_directory:
            # If no original path but we have the directory, use directory + suggested filename
            initial_path = str(Path(self._current_pdf_directory) / filename)
        else:
            # Fallback to just the filename (will use current working directory)
            initial_path = filename

        # Show save dialog
        from .ui_translations import get_translations
        ui_tr = get_translations()

        save_path, _ = QFileDialog.getSaveFileName(
            self.parent(),
            ui_tr['save_pdf_title'],
            initial_path,
            ui_tr['pdf_files_filter']
        )

        if save_path:
            try:
                # Write file
                with open(save_path, 'wb') as f:
                    f.write(data)

                # Emit backend signal
                self.save_requested.emit(data, save_path)
            except Exception as e:
                self.error_occurred.emit(f"Failed to save PDF: {e}")

    def _on_print_requested(self, data: bytes):
        """Handle print request from bridge.

        Args:
            data: PDF data with annotations.
        """
        # Store PDF data for printing
        self._last_print_data = data

        # Emit signal for external handlers
        self.print_requested.emit(data)

        # Get original filename for temp file
        filename = "document.pdf"
        if self._current_pdf_url:
            from pathlib import Path
            if self._current_pdf_url.startswith('file://'):
                filename = Path(self._current_pdf_url.replace('file://', '')).name
            elif not self._current_pdf_url.startswith('data:'):
                filename = Path(self._current_pdf_url).name

        # Route to appropriate print handler
        try:
            if self.config.print_handler == PrintHandler.SYSTEM:
                self._print_with_system_handler(data, filename)
            elif self.config.print_handler == PrintHandler.QT_DIALOG:
                self._print_with_qt_dialog(data)
            elif self.config.print_handler == PrintHandler.EMIT_SIGNAL:
                self._print_with_signal_emission(data, filename)
        except Exception as e:
            self.error_occurred.emit(f"Print handler error: {e}")

    def _on_load_requested(self, path: str):
        """Handle load request from bridge."""
        try:
            self.load_pdf(path)
        except Exception as e:
            self.error_occurred.emit(f"Failed to load PDF: {e}")

    def _on_pdf_loaded(self, metadata: dict):
        """Handle PDF loaded event from bridge."""
        # Store metadata for potential recovery after crash
        self._pdf_metadata = metadata
        self._total_pages = metadata.get('numPages', 0)
        self._current_page = 1  # Begin at first page for new document

        self.pdf_loaded.emit(metadata)

    def _on_annotation_changed(self):
        """Handle annotation changed event from bridge."""
        self._has_annotations = True
        self.annotation_modified.emit()

    def _on_page_changed(self, current: int, total: int):
        """Handle page changed event from bridge."""
        # Track current page position for potential restoration
        self._current_page = current
        self._total_pages = total

        self.page_changed.emit(current, total)

    def _on_error_occurred(self, message: str):
        """Handle error from bridge."""
        self.error_occurred.emit(message)

    def _on_text_copied(self, text: str):
        """Handle text copied to clipboard.

        Args:
            text: The text that was copied.
        """
        # Show a brief notification overlay
        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import QTimer, Qt
        from PySide6.QtGui import QFont

        parent_widget = self.parent()
        if not parent_widget:
            return

        # Create notification label
        notification = QLabel(self.tr['text_copied'], parent_widget)
        notification.setStyleSheet("""
            QLabel {
                background-color: rgba(50, 50, 50, 220);
                color: white;
                padding: 12px 20px;
                border-radius: 8px;
                font-size: 14px;
            }
        """)
        notification.setFont(QFont("Sans Serif", 11))
        notification.setAlignment(Qt.AlignmentFlag.AlignCenter)
        notification.adjustSize()

        # Position at bottom center
        x = (parent_widget.width() - notification.width()) // 2
        y = parent_widget.height() - notification.height() - 50
        notification.move(x, y)
        notification.show()

        # Auto-hide after 5 seconds
        QTimer.singleShot(5000, notification.deleteLater)

    # Crash detection and recovery
    def _on_render_process_terminated(self, termination_status, exit_code):
        """Handle renderer process termination and attempt recovery.

        Args:
            termination_status: Qt termination status enum
            exit_code: Process exit code
        """
        from PySide6.QtWebEngineCore import QWebEnginePage

        # Determine if this was a crash or normal termination
        if termination_status == QWebEnginePage.RenderProcessTerminationStatus.CrashedTerminationStatus:
            self.error_occurred.emit("WebEngine renderer process crashed")
            self.renderer_crashed.emit()

            # Attempt automatic recovery if PDF was loaded
            if self._current_pdf_url and not self._is_recovering_from_crash:
                self._recover_from_crash()

        elif termination_status == QWebEnginePage.RenderProcessTerminationStatus.AbnormalTerminationStatus:
            self.error_occurred.emit(f"WebEngine renderer terminated abnormally (exit code: {exit_code})")
            self.renderer_crashed.emit()

            if self._current_pdf_url and not self._is_recovering_from_crash:
                self._recover_from_crash()

    def _recover_from_crash(self):
        """Attempt to recover from a renderer crash by recreating the page.

        This method:
        1. Recreates the WebEngine page
        2. Reloads the viewer
        3. Restores the PDF
        4. Attempts to restore the page position
        """
        from PySide6.QtCore import QTimer

        self._is_recovering_from_crash = True

        try:
            # Save current state
            saved_pdf_url = self._current_pdf_url
            saved_page = self._current_page

            # Recreate the web view with same configuration
            self._setup_web_view()
            self._setup_bridge()

            # Reload viewer (triggers JavaScript load)
            self._load_viewer()

            # Wait for viewer to initialize, then restore PDF
            def restore_pdf():
                try:
                    if saved_pdf_url:
                        # Reload the PDF
                        if saved_pdf_url.startswith('data:'):
                            # Can't restore data URLs after crash
                            self.error_occurred.emit("Cannot restore PDF from memory after crash")
                        else:
                            # Restore file-based PDF
                            self.web_view.load(QUrl(saved_pdf_url))

                            # Try to restore page position after a delay
                            if saved_page > 1:
                                QTimer.singleShot(2000, lambda: self.goto_page(saved_page))

                except Exception as e:
                    self.error_occurred.emit(f"Failed to restore PDF after crash: {e}")
                finally:
                    self._is_recovering_from_crash = False

            # Wait 1 second for viewer to initialize
            QTimer.singleShot(1000, restore_pdf)

        except Exception as e:
            self.error_occurred.emit(f"Crash recovery failed: {e}")
            self._is_recovering_from_crash = False

    def _cleanup_before_shutdown(self):
        """Perform graceful cleanup before shutdown.

        This method ensures resources are released properly to prevent
        shutdown crashes (Speicherzugriffsfehler).
        """
        from PySide6.QtCore import QCoreApplication

        # Clean up temporary PDF file first
        self._cleanup_temp_pdf()

        try:
            # Stop any ongoing JavaScript execution
            if self.web_view and self.web_view.page():
                js_code = '''
                (function() {
                    if (typeof PDFViewerApplication !== 'undefined') {
                        try {
                            PDFViewerApplication.close();
                        } catch(e) {}
                    }
                })();
                '''
                self.web_view.page().runJavaScript(js_code)

            # Process events to allow cleanup
            QCoreApplication.processEvents()

            # Disconnect signals
            if self.web_view and self.web_view.page():
                try:
                    self.web_view.page().renderProcessTerminated.disconnect()
                except:
                    pass

            # Now call regular cleanup
            self.cleanup()

        except Exception as e:
            # Suppress errors during shutdown
            pass


# Register the backend
register_backend("inprocess", InProcessBackend)
