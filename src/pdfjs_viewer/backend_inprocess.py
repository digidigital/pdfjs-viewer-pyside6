"""In-process backend using QWebEngineView.

This backend runs PDF.js in a QWebEngineView within the main process.
It provides full functionality but shares the main process memory space.
"""

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union

from PySide6.QtCore import QUrl, QUrlQuery, QTimer
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMessageBox, QFileDialog

from .viewer_backend import ViewerBackend, register_backend
from .bridge import PDFJavaScriptBridge
from .config import PDFViewerConfig, PrintHandler
from .print_utils import get_temp_file_manager
from .print_manager import PrintManager
from .resources import PDFResourceManager
from .security import PDFSecurityManager
from .ui_translations import get_translations
from .print_translations import get_translation
from .unsaved_changes_dialog import UnsavedChangesDialog
from .annotation_tracker import AnnotationStateTracker


def _get_real_home_directory() -> str:
    """Get the user's real home directory, handling snap confinement.

    In snap packages, Path.home() returns the snap's confined home directory
    (e.g., ~/snap/appname/current). This function returns the actual user
    home directory by checking SNAP_REAL_HOME environment variable first.

    Returns:
        Path to the user's real home directory.
    """
    # Check for snap's real home environment variable
    snap_real_home = os.environ.get('SNAP_REAL_HOME')
    if snap_real_home:
        return snap_real_home

    # Fall back to standard home directory (works on all platforms)
    return str(Path.home())


def _get_clean_subprocess_env():
    """Get a clean environment for spawning system subprocesses.

    PyInstaller injects LD_LIBRARY_PATH (Linux) and DYLD_LIBRARY_PATH /
    DYLD_FRAMEWORK_PATH (macOS) pointing to its bundled libraries.  Child
    processes such as xdg-open or open inherit these variables, which can
    cause the system PDF viewer to load incompatible libraries and fail.

    PyInstaller stores the original values as ``*_ORIG`` environment
    variables.  This function restores them so that child processes see
    the user's original library paths.

    Returns:
        A cleaned copy of ``os.environ``, or ``None`` if no cleaning is
        needed (unfrozen environment or Windows).
    """
    if not getattr(sys, 'frozen', False):
        return None

    system = platform.system()
    if system == 'Windows':
        return None

    env = os.environ.copy()

    if system == 'Linux':
        vars_to_clean = ['LD_LIBRARY_PATH']
    elif system == 'Darwin':
        vars_to_clean = ['DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH']
    else:
        return None

    for var in vars_to_clean:
        orig_key = f'{var}_ORIG'
        if orig_key in env:
            orig_value = env[orig_key]
            if orig_value:
                env[var] = orig_value
            else:
                env.pop(var, None)
            env.pop(orig_key, None)
        elif var in env:
            # No _ORIG means it was not set before PyInstaller — remove
            env.pop(var, None)

    return env


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

        # Temporary file management for performance
        self._temp_pdf_path: Optional[Path] = None  # Temp copy of PDF
        self._original_pdf_path: Optional[Path] = None  # Original PDF location
        self._load_in_progress = False  # Reentrancy guard for load operations

        # Async save state: instead of blocking the main thread waiting for JS
        # to produce PDF data, we trigger PDFViewerApplication.download() and
        # let the bridge's save_requested signal deliver the data asynchronously.
        # _save_mode controls how _on_save_requested routes the incoming data.
        self._save_mode = 'normal'  # 'normal' | 'auto_save' | 'save_as' | 'print'
        self._save_target: Optional[Path] = None  # Target path for auto_save
        self._pending_load: Optional[dict] = None  # Deferred load_pdf params
        self._close_deferred = False  # Whether close is waiting for async save
        self._save_timeout_timer = None  # QTimer for async save timeout

        # Print manager for separate process printing
        self._print_manager: Optional[PrintManager] = None

        # Track state for crash recovery (page position, metadata, recovery flag)
        self._current_page: int = 1
        self._total_pages: int = 0
        self._pdf_metadata: Optional[dict] = None
        self._is_recovering_from_crash: bool = False

        # Qt-side annotation state tracking (independent of PDF.js internals)
        self._annotation_tracker = AnnotationStateTracker(self)

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
        """Setup the QWebEngineView with safe stability defaults."""
        from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
        import uuid

        # Always create isolated profile with unique name for stability
        profile_name = f"pdfjs_viewer_{uuid.uuid4().hex[:8]}"
        profile = QWebEngineProfile(profile_name, self.parent())

        # Disable cache and persistent storage
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
        profile.setPersistentStoragePath("")

        # Create secure page with profile
        secure_page = self.security_manager.create_page(profile=profile, parent=self.parent())

        # Store references for proper cleanup
        self._page = secure_page
        self._profile = profile

        # Configure WebEngine settings for stability
        settings = secure_page.settings()

        # Disable crash-prone features
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, False)
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
        self.bridge.print_pdf_requested.connect(self._on_print_pdf_requested)
        self.bridge.load_requested.connect(self._on_load_requested)
        self.bridge.open_pdf_requested.connect(self._on_open_pdf_requested)
        self.bridge.pdf_loaded.connect(self._on_pdf_loaded)
        self.bridge.annotation_changed.connect(self._on_annotation_changed)
        self.bridge.page_changed.connect(self._on_page_changed)
        self.bridge.error_occurred.connect(self._on_error_occurred)
        self.bridge.text_copied.connect(self._on_text_copied)
        self.bridge.save_started.connect(self._on_save_started)

        # Connect annotation tracking - mark tracker as modified when JS reports changes
        self.bridge.annotation_changed.connect(self._annotation_tracker.mark_modified)

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

        If the current document has unsaved changes and unsaved_changes_action is
        configured, the user will be prompted before loading the new PDF.

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
        # Reentrancy guard: prevents double-loading when multiple signals
        # (e.g. clicked + selectionChanged) fire for the same user action.
        if self._load_in_progress:
            return

        # If an async save is already in progress, replace the pending load
        # with this newer request (last-write-wins). The save will complete
        # and then load this file instead of the previously pending one.
        if self._save_mode != 'normal':
            self._pending_load = {
                'type': 'load_pdf', 'file_path': file_path,
                'page': page, 'zoom': zoom,
                'pagemode': pagemode, 'nameddest': nameddest
            }
            return

        self._load_in_progress = True
        try:
            # Handle unsaved changes — may trigger async save and defer this load
            result = self._handle_unsaved_before_action(
                pending_action={'type': 'load_pdf', 'file_path': file_path,
                                'page': page, 'zoom': zoom,
                                'pagemode': pagemode, 'nameddest': nameddest}
            )
            if result == 'deferred':
                return  # Save in progress, load will happen when save completes
            if result == 'cancelled':
                return  # User cancelled Save As dialog

            # No unsaved changes or user discarded — proceed immediately
            self._execute_load_pdf(file_path, page, zoom, pagemode, nameddest)
        finally:
            self._load_in_progress = False

    def _execute_load_pdf(
        self,
        file_path: str,
        page: Optional[int] = None,
        zoom: Optional[Union[str, int, float]] = None,
        pagemode: Optional[str] = None,
        nameddest: Optional[str] = None
    ):
        """Execute the actual PDF loading (no unsaved changes check).

        This is the core loading logic, separated from load_pdf() so it can be
        called both synchronously (no unsaved changes) and deferred (after async
        save completes).
        """
        from .config import validate_pdf_file

        path = Path(file_path)

        # Handle UNC paths on Windows
        if str(path).startswith('\\\\'):
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

        # Reset annotation tracker for the new document
        # Use file path hash as document identifier
        import hashlib
        doc_id = hashlib.md5(str(path).encode()).hexdigest()
        self._annotation_tracker.set_document(doc_id)

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

        If the current document has unsaved changes and unsaved_changes_action is
        configured, the user will be prompted before loading the new PDF.

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
        # Same reentrancy guard as load_pdf (see comment there)
        if self._load_in_progress:
            return

        # If async save in progress, replace pending load (last-write-wins)
        if self._save_mode != 'normal':
            self._pending_load = {
                'type': 'load_pdf_bytes', 'pdf_data': pdf_data,
                'filename': filename, 'page': page, 'zoom': zoom,
                'pagemode': pagemode, 'nameddest': nameddest
            }
            return

        self._load_in_progress = True
        try:
            result = self._handle_unsaved_before_action(
                pending_action={'type': 'load_pdf_bytes', 'pdf_data': pdf_data,
                                'filename': filename, 'page': page, 'zoom': zoom,
                                'pagemode': pagemode, 'nameddest': nameddest}
            )
            if result == 'deferred':
                return
            if result == 'cancelled':
                return

            self._execute_load_pdf_bytes(pdf_data, filename, page, zoom,
                                         pagemode, nameddest)
        finally:
            self._load_in_progress = False

    def _execute_load_pdf_bytes(
        self,
        pdf_data: bytes,
        filename: str = "document.pdf",
        page: Optional[int] = None,
        zoom: Optional[Union[str, int, float]] = None,
        pagemode: Optional[str] = None,
        nameddest: Optional[str] = None
    ):
        """Execute the actual PDF-from-bytes loading (no unsaved changes check)."""
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

            # Reset annotation tracker for the new document
            # Use content hash as document identifier for bytes
            import hashlib
            doc_id = hashlib.md5(pdf_data[:1024]).hexdigest()  # Hash first 1KB for efficiency
            self._annotation_tracker.set_document(doc_id)

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
        if self._load_in_progress:
            return
        # If async save in progress, defer blank page as pending action
        if self._save_mode != 'normal':
            self._pending_load = {'type': 'show_blank_page'}
            return

        # Clean up temp file when closing PDF
        self._cleanup_temp_pdf()

        self._current_pdf_url = None
        self._original_pdf_path = None
        self._current_pdf_directory = None

        # Reset annotation tracker since we're leaving the document
        self._annotation_tracker.reset()

        # Reload viewer with empty file parameter to prevent demo PDF from loading
        # PDF.js loads "compressed.tracemonkey-pldi-09.pdf" by default if no file param
        viewer_url = self.resource_manager.get_viewer_url()
        query = QUrlQuery()
        query.addQueryItem('file', '')  # Empty file parameter prevents default PDF
        viewer_qurl = QUrl(viewer_url)
        viewer_qurl.setQuery(query)
        self.web_view.setUrl(viewer_qurl)

    def print_pdf(self):
        """Trigger print for current PDF.

        Triggers PDFViewerApplication.download() to get PDF data with annotations,
        then asynchronously feeds it to the print handler when the data arrives
        via the bridge's save_requested signal.
        """
        self._do_print_pdf()

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
            except (RuntimeError, TypeError):
                # RuntimeError: signal not connected, TypeError: wrong signature
                pass

        # Delete page BEFORE profile (critical for proper cleanup)
        if self._page:
            try:
                self._page.deleteLater()
            except RuntimeError:
                # Object already deleted
                pass
            self._page = None

        # Delete profile after page
        if self._profile:
            try:
                # Only delete if it's not the default profile
                from PySide6.QtWebEngineCore import QWebEngineProfile
                if self._profile != QWebEngineProfile.defaultProfile():
                    self._profile.deleteLater()
            except RuntimeError:
                # Object already deleted
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
        except (OSError, RuntimeError, AttributeError):
            # OSError: file operation failed, RuntimeError: Qt object deleted,
            # AttributeError: attribute already cleaned up during shutdown
            pass

    def has_annotations(self) -> bool:
        """Check if current PDF has annotations.

        Delegates to the AnnotationStateTracker which monitors annotation
        changes reported by JavaScript through the bridge.

        Returns:
            True if PDF has been annotated, False otherwise.
        """
        return self._annotation_tracker.has_unsaved_changes()

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
            try:
                count = len(pdf)
                return count
            finally:
                pdf.close()
        except (ImportError, Exception):
            # Fallback: try pikepdf
            try:
                import pikepdf
                import io
                with pikepdf.open(io.BytesIO(data)) as pdf:
                    return len(pdf.pages)
            except (ImportError, Exception):
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

            # In PyInstaller frozen builds, child processes inherit library
            # path overrides that can break the system viewer.
            clean_env = _get_clean_subprocess_env()

            try:
                if system == 'Linux':
                    proc = subprocess.Popen(
                        ['xdg-open', str(temp_path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        env=clean_env,
                    )
                    self._check_system_viewer_result(proc, 'xdg-open')
                elif system == 'Darwin':  # macOS
                    proc = subprocess.Popen(
                        ['open', str(temp_path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        env=clean_env,
                    )
                    self._check_system_viewer_result(proc, 'open')
                elif system == 'Windows':
                    os.startfile(str(temp_path))
                else:
                    self.error_occurred.emit(f"Unsupported platform: {system}")
            except FileNotFoundError as e:
                self.error_occurred.emit(f"System PDF viewer not found: {e}")
            except OSError as e:
                self.error_occurred.emit(f"Failed to open PDF viewer: {e}")

        except Exception as e:
            self.error_occurred.emit(f"System print error: {e}")

    def _check_system_viewer_result(self, proc, command_name: str):
        """Check if a system viewer subprocess exited with an error.

        Uses a brief timer so the main event loop is not blocked.  If the
        process is still running after the delay it is assumed to have
        launched successfully.

        Args:
            proc: The ``subprocess.Popen`` instance to monitor.
            command_name: Human-readable name for error messages.
        """
        def _check():
            retcode = proc.poll()
            if retcode is not None and retcode != 0:
                stderr_output = ''
                try:
                    stderr_output = proc.stderr.read().decode(
                        'utf-8', errors='ignore'
                    ).strip()
                except Exception:
                    pass
                error_msg = f"{command_name} failed (exit code {retcode})"
                if stderr_output:
                    error_msg += f": {stderr_output}"
                self.error_occurred.emit(error_msg)

        QTimer.singleShot(3000, _check)

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
                timeout_ms=300000,  # 5 minute timeout
                print_dpi=self.config.print_dpi,
                print_fit_to_page=self.config.print_fit_to_page,
                print_parallel_pages=self.config.print_parallel_pages
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
        """Handle save request from bridge — central routing for all save operations.

        This method is the single handler for bridge.save_requested. It routes
        incoming PDF data based on _save_mode:

        - 'normal': User clicked the PDF.js download button → show Save As dialog
        - 'auto_save': Async auto-save in progress → write to _save_target
        - 'save_as': Async Save As in progress → show Save As dialog then complete
        - 'print': Async print in progress → send data to print handler

        After handling the data, this method completes any deferred action
        (pending load, pending close) stored in _pending_load/_close_deferred.

        Args:
            data: PDF data with annotations.
            filename: Suggested filename.
        """
        # Save arrived — cancel the timeout timer
        self._stop_save_timeout()

        mode = self._save_mode

        if mode == 'auto_save':
            self._complete_auto_save(data)
        elif mode == 'save_as':
            self._complete_save_as(data, filename)
        elif mode == 'print':
            self._complete_print(data)
        else:
            # Normal mode: user clicked download button in PDF.js toolbar
            self._do_normal_save(data, filename)

    def _do_normal_save(self, data: bytes, filename: str):
        """Handle normal save (user clicked download button in PDF.js).

        Shows a Save As dialog and writes the file.

        Args:
            data: PDF data with annotations.
            filename: Suggested filename.
        """
        # Use original PDF path if available, otherwise construct from directory + filename
        if self._original_pdf_path and self._original_pdf_path.exists():
            initial_path = str(self._original_pdf_path)
        elif self._current_pdf_directory:
            initial_path = str(Path(self._current_pdf_directory) / filename)
        else:
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
                with open(save_path, 'wb') as f:
                    f.write(data)

                # Mark annotations as saved in Qt tracker
                self._annotation_tracker.mark_saved()

                # Emit backend signal
                self.save_requested.emit(data, save_path)
            except Exception as e:
                self.error_occurred.emit(f"Failed to save PDF: {e}")

    def _complete_auto_save(self, data: bytes):
        """Complete an async auto-save operation.

        Writes PDF data to the previously captured _save_target path,
        then executes any pending load or close action.

        Args:
            data: PDF data with annotations.
        """
        save_target = self._save_target
        self._save_mode = 'normal'
        self._save_target = None

        if not save_target:
            self.error_occurred.emit("Auto-save failed: no target path")
            self._cancel_pending_action()
            return

        try:
            with open(save_target, 'wb') as f:
                f.write(data)

            # Mark annotations as saved
            self._annotation_tracker.mark_saved()
            self._mark_annotations_saved()
            self._suppress_beforeunload()

        except PermissionError:
            self.error_occurred.emit(
                f"Cannot write to {save_target}. Save As fallback."
            )
            # Fall back to Save As
            self._save_mode = 'save_as'
            # Data is already available, handle it directly
            self._complete_save_as(data, save_target.name)
            return

        except Exception as e:
            self.error_occurred.emit(f"Auto-save failed: {e}")
            self._cancel_pending_action()
            return

        # Execute deferred action
        self._execute_pending_action()

    def _complete_save_as(self, data: bytes, filename: str):
        """Complete an async Save As operation.

        Shows a Save As dialog, writes the file, then executes any pending action.

        Args:
            data: PDF data with annotations.
            filename: Suggested filename.
        """
        self._save_mode = 'normal'
        self._save_target = None

        # Determine initial path for save dialog
        if self._original_pdf_path and self._original_pdf_path.exists():
            initial_path = str(self._original_pdf_path)
        elif self._current_pdf_directory:
            initial_path = str(Path(self._current_pdf_directory) / filename)
        else:
            initial_path = filename

        save_path, _ = QFileDialog.getSaveFileName(
            self.parent(),
            self.tr['save_pdf_title'],
            initial_path,
            self.tr['pdf_files_filter']
        )

        if not save_path:
            # User cancelled Save As — cancel the pending action too
            self._cancel_pending_action()
            return

        try:
            with open(save_path, 'wb') as f:
                f.write(data)

            self._annotation_tracker.mark_saved()
            self._mark_annotations_saved()
            self._suppress_beforeunload()

        except Exception as e:
            self.error_occurred.emit(f"Failed to save PDF: {e}")
            self._cancel_pending_action()
            return

        # Execute deferred action
        self._execute_pending_action()

    def _complete_print(self, data: bytes):
        """Complete an async print operation.

        Sends PDF data to the print handler.

        Args:
            data: PDF data with annotations.
        """
        self._save_mode = 'normal'

        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        QApplication.restoreOverrideCursor()

        if data:
            self._on_print_requested(data)
        else:
            self.error_occurred.emit("Failed to get PDF data for printing")

    # Acknowledgment timeout (ms). If JS doesn't call notify_save_started
    # within this time, the JS environment is considered dead and the save
    # is skipped. This is short because performDownload() calls
    # notify_save_started immediately before doing any heavy work.
    _SAVE_ACK_TIMEOUT_MS = 2000  # 2 seconds

    def _trigger_js_download(self):
        """Trigger PDFViewerApplication.download() in JavaScript.

        This calls the exact same code path as the manual download button in
        PDF.js. The interceptor has overridden download() to call
        performDownload(), which does: notify_save_started → exit edit mode →
        saveDocument() → base64 encode → bridge.save_pdf(). The bridge's
        save_pdf slot then emits save_requested, which is handled by
        _on_save_requested.

        This is non-blocking — the method returns immediately and the data
        arrives asynchronously via the save_requested signal.

        A two-phase timeout protects against JS failure:
        - Phase 1 (ack, 2s): If JS never calls notify_save_started, the
          request didn't reach performDownload(). Save is skipped.
        - Phase 2 (no timeout): Once JS acknowledges, saveDocument() may
          take arbitrarily long for large PDFs. We wait indefinitely.
        """
        if not self.web_view or not self.web_view.page():
            return

        # Start ack timeout — JS should call notify_save_started quickly
        self._save_timeout_timer = QTimer(self)
        self._save_timeout_timer.setSingleShot(True)
        self._save_timeout_timer.timeout.connect(self._on_save_ack_timeout)
        self._save_timeout_timer.start(self._SAVE_ACK_TIMEOUT_MS)

        self.web_view.page().runJavaScript(
            "if (typeof window.PDFViewerApplication !== 'undefined'"
            " && window.PDFViewerApplication.pdfDocument) {"
            "  PDFViewerApplication.download();"
            "}"
        )

    def _on_save_started(self):
        """Handle acknowledgment from JS that performDownload() is running.

        Cancels the ack timeout. From here, saveDocument() may take
        arbitrarily long — we don't impose a completion timeout because
        large PDFs legitimately need more time.
        """
        self._stop_save_timeout()

    def _on_save_ack_timeout(self):
        """Handle timeout when JS never acknowledged the save request.

        This means performDownload() was never entered — the JS environment
        is broken (e.g., web view navigated away, PDF.js not loaded).
        Resets save state and executes any pending action without saving.
        """
        print('Save skipped: JS did not acknowledge download request')
        self._save_mode = 'normal'
        self._save_target = None
        self._save_timeout_timer = None

        from PySide6.QtWidgets import QApplication
        QApplication.restoreOverrideCursor()

        self._execute_pending_action()

    def _stop_save_timeout(self):
        """Stop the save timeout timer if it's running."""
        if self._save_timeout_timer is not None:
            self._save_timeout_timer.stop()
            self._save_timeout_timer = None

    def _execute_pending_action(self):
        """Execute a deferred action after async save completes.

        Handles pending load_pdf, load_pdf_bytes, or close operations
        that were deferred while waiting for save data.
        """
        pending_load = self._pending_load
        pending_close = self._close_deferred
        self._pending_load = None
        self._close_deferred = None

        if pending_load:
            action_type = pending_load.pop('type')
            try:
                if action_type == 'load_pdf':
                    self._execute_load_pdf(**pending_load)
                elif action_type == 'load_pdf_bytes':
                    self._execute_load_pdf_bytes(**pending_load)
                elif action_type == 'show_blank_page':
                    self.show_blank_page()
            except Exception as e:
                self.error_occurred.emit(f"Failed to load PDF: {e}")
        elif pending_close:
            # Re-trigger close on the widget — unsaved changes are now handled
            widget = self.parent()
            if widget:
                widget.close()

    def _cancel_pending_action(self):
        """Cancel a deferred action (e.g. when Save As is cancelled).

        Resets all async save state and pending action state.
        """
        self._stop_save_timeout()
        self._save_mode = 'normal'
        self._save_target = None
        self._pending_load = None
        self._close_deferred = False

    def _on_print_requested(self, data: bytes):
        """Handle print request from bridge.

        Args:
            data: PDF data with annotations.
        """
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
        """Handle load request from bridge.

        Uses QTimer.singleShot to break out of the JavaScript callback chain.
        load_pdf() handles unsaved changes internally via the async pattern.
        """
        from PySide6.QtCore import QTimer

        def do_load():
            try:
                self.load_pdf(path)
            except Exception as e:
                self.error_occurred.emit(f"Failed to load PDF: {e}")

        # Defer to next event loop iteration to break out of JS callback chain
        QTimer.singleShot(0, do_load)

    def _on_open_pdf_requested(self):
        """Handle open PDF request from PDF.js load button.

        Shows file dialog first, then calls load_pdf() which handles
        unsaved changes internally via the async pattern.

        Uses QTimer.singleShot to break out of the JavaScript callback chain.
        """
        from PySide6.QtCore import QTimer

        def do_open():
            try:
                # Show file dialog first
                initial_dir = self._current_pdf_directory or _get_real_home_directory()
                file_path, _ = QFileDialog.getOpenFileName(
                    self.parent(),
                    self.tr['open_pdf_title'],
                    initial_dir,
                    self.tr['pdf_files_filter']
                )

                if file_path:
                    # load_pdf handles unsaved changes via async pattern
                    self.load_pdf(file_path)
            except Exception as e:
                self.error_occurred.emit(f"Failed to open PDF: {e}")

        # Defer to next event loop iteration to break out of JS callback chain
        QTimer.singleShot(0, do_open)

    def _on_print_pdf_requested(self):
        """Handle print PDF request from PDF.js print button.

        This triggers the same flow as clicking a Qt "Print" button.
        Uses QTimer.singleShot to break out of the JavaScript callback chain.
        """
        from PySide6.QtCore import QTimer

        # Defer to next event loop iteration to break out of JS callback chain
        QTimer.singleShot(0, self._do_print_pdf)

    def _do_print_pdf(self):
        """Execute print flow: trigger async PDF data capture, then print.

        This is the shared implementation for both Qt print button and PDF.js
        print button. It sets _save_mode to 'print' and triggers
        PDFViewerApplication.download(). When the data arrives via
        save_requested, _complete_print() sends it to the print handler.
        """
        # Early check: don't proceed if no PDF is loaded or save already in progress
        if not self._current_pdf_url:
            self.error_occurred.emit("No PDF loaded")
            return
        if self._save_mode != 'normal':
            return

        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt

        # Show busy cursor — will be restored in _complete_print()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        self._save_mode = 'print'
        self._trigger_js_download()

    def _on_pdf_loaded(self, metadata: dict):
        """Handle PDF loaded event from bridge."""
        # Store metadata for potential recovery after crash
        self._pdf_metadata = metadata
        self._total_pages = metadata.get('numPages', 0)
        self._current_page = 1  # Begin at first page for new document

        self.pdf_loaded.emit(metadata)

    def _on_annotation_changed(self):
        """Handle annotation changed event from bridge."""
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

    # Unsaved changes handling
    def _exit_annotation_edit_mode(self):
        """Exit annotation edit mode in PDF.js to commit in-progress annotations.

        This dispatches a switchannotationeditormode event to PDF.js which:
        1. Commits any annotation currently being edited
        2. Writes the data to AnnotationStorage (triggers onSetModified)
        3. onSetModified fires notify_annotation_changed on the bridge
        4. The bridge signal updates our AnnotationStateTracker

        This method blocks briefly (up to 500ms) to ensure the JS executes
        and the bridge signal propagates back to Qt. This is safe because
        it's only called from Qt-initiated contexts (load_pdf, close button),
        never from JS callbacks.
        """
        if not self.web_view or not self.web_view.page():
            return

        # Exit edit mode and return whether mode was active
        js_code = """
        (function() {
            const app = window.PDFViewerApplication;
            if (app && app.pdfViewer) {
                const currentMode = app.pdfViewer.annotationEditorMode;
                if (currentMode && currentMode > 0) {
                    if (app.eventBus) {
                        app.eventBus.dispatch('switchannotationeditormode', {
                            source: app,
                            mode: 0
                        });
                    }
                    return true;
                }
            }
            return false;
        })();
        """
        was_in_edit_mode = [None]

        def callback(result):
            was_in_edit_mode[0] = result

        self.web_view.page().runJavaScript(js_code, callback)

        # Wait for JS to execute and bridge signal to propagate.
        # We need two things to happen:
        # 1. The JS switchannotationeditormode event commits the annotation
        # 2. onSetModified fires → bridge.notify_annotation_changed → tracker update
        # Both happen asynchronously, so we processEvents until the callback fires.
        from PySide6.QtWidgets import QApplication
        import time
        deadline = time.monotonic() + 0.5  # 500ms max wait
        while was_in_edit_mode[0] is None and time.monotonic() < deadline:
            QApplication.processEvents()

        # If edit mode was active, give extra time for the bridge signal to arrive
        if was_in_edit_mode[0]:
            extra_deadline = time.monotonic() + 0.2  # 200ms for bridge propagation
            while time.monotonic() < extra_deadline:
                QApplication.processEvents()

    def has_unsaved_changes(self) -> bool:
        """Check if document has unsaved annotations.

        Uses Qt-side AnnotationStateTracker which monitors annotation changes
        reported by JavaScript through the bridge. This is more reliable than
        querying PDF.js internal state directly.

        The tracker is:
        - Marked as modified when JS reports annotation changes
        - Reset when a new PDF is loaded
        - Cleared when a save completes successfully

        Returns:
            True if there are unsaved changes, False otherwise.
        """
        return self._annotation_tracker.has_unsaved_changes()

    def _handle_unsaved_before_action(self, pending_action: dict) -> str:
        """Check for unsaved changes and either proceed, defer, or cancel.

        This is the core decision method called by load_pdf/load_pdf_bytes
        before navigating. It shows the prompt dialog (if configured),
        determines the save mode, and either:
        - Returns 'proceed' if no save needed (no changes, disabled, discard)
        - Returns 'deferred' if async save was triggered (caller should return)
        - Returns 'cancelled' if user cancelled Save As dialog

        The actual save is asynchronous: we set _save_mode and call
        _trigger_js_download(). When the data arrives via save_requested,
        _on_save_requested routes it to _complete_auto_save/_complete_save_as,
        which then calls _execute_pending_action() to do the deferred load.

        Args:
            pending_action: Dict describing the action to defer. Must contain
                'type' key ('load_pdf' or 'load_pdf_bytes') plus the method's kwargs.

        Returns:
            'proceed': Safe to continue immediately (no unsaved changes or discarded)
            'deferred': Async save triggered, action stored in _pending_load
            'cancelled': User cancelled the Save As dialog
        """
        action = self.config.features.unsaved_changes_action

        if action == "disabled":
            self._suppress_beforeunload()
            return 'proceed'

        # Exit annotation edit mode first to commit any in-progress annotations
        self._exit_annotation_edit_mode()

        if not self.has_unsaved_changes():
            return 'proceed'

        if action == "auto_save":
            # Check if we have an original file path to overwrite
            if not self._original_pdf_path or not self._original_pdf_path.exists():
                # No original file — need Save As, which is also async
                self._save_mode = 'save_as'
            else:
                self._save_mode = 'auto_save'
                self._save_target = self._original_pdf_path

            self._pending_load = pending_action
            self._trigger_js_download()
            return 'deferred'

        if action == "prompt":
            dialog = UnsavedChangesDialog(self.parent())
            result = dialog.get_result()

            if result == UnsavedChangesDialog.SAVE_AS:
                self._save_mode = 'save_as'
                self._pending_load = pending_action
                self._trigger_js_download()
                return 'deferred'

            elif result == UnsavedChangesDialog.SAVE:
                if not self._original_pdf_path or not self._original_pdf_path.exists():
                    self._save_mode = 'save_as'
                else:
                    self._save_mode = 'auto_save'
                    self._save_target = self._original_pdf_path

                self._pending_load = pending_action
                self._trigger_js_download()
                return 'deferred'

            else:  # DISCARD
                self._annotation_tracker.reset()
                self._suppress_beforeunload()
                return 'proceed'

        return 'proceed'

    def handle_unsaved_changes(self) -> bool:
        """Handle unsaved changes according to config (for external callers).

        This is the public API called by closeEvent and external code.
        For close operations, we still need synchronous behavior: show the
        dialog, trigger the save, and defer the actual close.

        For the common case of load_pdf triggering this, the internal
        _handle_unsaved_before_action is used instead.

        Returns:
            True if it's safe to proceed (no changes, discarded, or save triggered).
            False if Save As was cancelled by user.
        """
        # If an async save is already in progress, it's safe to proceed
        # (the pending action will complete when save finishes)
        if self._save_mode != 'normal':
            return True

        action = self.config.features.unsaved_changes_action

        if action == "disabled":
            self._suppress_beforeunload()
            return True

        # Exit annotation edit mode first
        self._exit_annotation_edit_mode()

        if not self.has_unsaved_changes():
            return True

        if action == "auto_save":
            if not self._original_pdf_path or not self._original_pdf_path.exists():
                self._save_mode = 'save_as'
            else:
                self._save_mode = 'auto_save'
                self._save_target = self._original_pdf_path
            # Store close as pending action
            self._close_deferred = True
            self._trigger_js_download()
            return False  # Caller should NOT proceed — close will be re-triggered

        if action == "prompt":
            dialog = UnsavedChangesDialog(self.parent())
            result = dialog.get_result()

            if result == UnsavedChangesDialog.SAVE_AS:
                self._save_mode = 'save_as'
                self._close_deferred = True
                self._trigger_js_download()
                return False

            elif result == UnsavedChangesDialog.SAVE:
                if not self._original_pdf_path or not self._original_pdf_path.exists():
                    self._save_mode = 'save_as'
                else:
                    self._save_mode = 'auto_save'
                    self._save_target = self._original_pdf_path
                self._close_deferred = True
                self._trigger_js_download()
                return False

            else:  # DISCARD
                self._annotation_tracker.reset()
                self._suppress_beforeunload()
                return True

        return True

    def _suppress_beforeunload(self):
        """Suppress the browser's beforeunload dialog.

        This clears PDF.js internal state that triggers the beforeunload confirmation.
        The JavaScript side (interceptor.js) handles preventing the event itself.
        """
        if self.web_view and self.web_view.page():
            # Call suppressBeforeUnload which clears PDF.js internal flags
            self.web_view.page().runJavaScript(
                "if (typeof window.suppressBeforeUnload === 'function') window.suppressBeforeUnload();"
            )

    def _mark_annotations_saved(self):
        """Mark annotations as saved in JavaScript."""
        if self.web_view and self.web_view.page():
            self.web_view.page().runJavaScript(
                "if (typeof window.markAnnotationsSaved === 'function') window.markAnnotationsSaved();"
            )

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
                except (RuntimeError, TypeError):
                    # RuntimeError: signal not connected, TypeError: wrong signature
                    pass

            # Now call regular cleanup
            self.cleanup()

        except Exception as e:
            # Suppress errors during shutdown
            pass


# Register the backend
register_backend("inprocess", InProcessBackend)
