"""Backend abstraction layer for PDF viewing.

This module provides an abstract interface that allows the PDFViewerWidget
to work with different backend implementations:
- InProcessBackend: QWebEngineView running in the main process (default)
- MultiProcessBackend: QWebEngineView running in a separate process (ultimate stability)

The abstraction allows switching between backends without changing the public API.
"""

from abc import ABCMeta, abstractmethod
from typing import Optional, Union
from PySide6.QtCore import QObject, Signal


# Create a metaclass that combines QObject's metaclass with ABCMeta
class QABCMeta(type(QObject), ABCMeta):
    """Metaclass that combines Qt's meta-object system with Python's ABC."""
    def __new__(mcls, name, bases, namespace, **kwargs):
        cls = super().__new__(mcls, name, bases, namespace, **kwargs)
        return cls


class ViewerBackend(QObject, metaclass=QABCMeta):
    """Abstract base class for PDF viewer backends.

    This interface defines the contract that all backends must implement.
    Backends handle the actual PDF rendering and interaction with PDF.js.

    Signals:
        pdf_loaded: Emitted when a PDF is successfully loaded.
            Args: metadata (dict) with keys: filename, numPages, title

        error_occurred: Emitted when an error occurs.
            Args: message (str) describing the error

        print_requested: Emitted when printing is requested (SYSTEM/QT_DIALOG handlers).
            Args: data (bytes) containing the PDF data

        print_data_ready: Emitted when print data is ready (EMIT_SIGNAL handler).
            Args: data (bytes), filename (str)

        save_requested: Emitted when saving is requested.
            Args: data (bytes), filename (str)

        annotation_modified: Emitted when annotations are added/modified.

        page_changed: Emitted when the current page changes.
            Args: current_page (int), total_pages (int)

        renderer_crashed: Emitted when the renderer process crashes.
            
    """

    # Signals that all backends must emit
    pdf_loaded = Signal(dict)  # metadata: {filename, numPages, title}
    error_occurred = Signal(str)  # error message
    print_requested = Signal(bytes)  # pdf_data for SYSTEM/QT_DIALOG
    print_data_ready = Signal(bytes, str)  # (pdf_data, filename) for EMIT_SIGNAL
    save_requested = Signal(bytes, str)  # (pdf_data, filename)
    annotation_modified = Signal()
    page_changed = Signal(int, int)  # (current_page, total_pages)
    renderer_crashed = Signal()  # Emitted when the renderer process crashes
    external_link_blocked = Signal(str)  # url that was blocked

    def __init__(self, parent: Optional[QObject] = None):
        """Initialize the backend.

        Args:
            parent: Parent QObject (usually the PDFViewerWidget)
        """
        super().__init__(parent)

    @abstractmethod
    def initialize(self, config, pdfjs_path: Optional[str] = None):
        """Initialize the backend with configuration.

        This is called after construction to set up the backend with the
        provided configuration. Separated from __init__ to allow proper
        signal connection before initialization.

        Args:
            config: PDFViewerConfig instance
            pdfjs_path: Optional custom path to PDF.js installation
        """
        pass

    @abstractmethod
    def load_pdf(
        self,
        file_path: str,
        page: Optional[int] = None,
        zoom: Optional[Union[str, int, float]] = None,
        pagemode: Optional[str] = None,
        nameddest: Optional[str] = None
    ):
        """Load a PDF file with optional viewer options.

        Args:
            file_path: Absolute path to the PDF file
            page: Page number to open (1-indexed)
            zoom: Zoom level - named or numeric
            pagemode: Sidebar state
            nameddest: Named destination

        Emits:
            pdf_loaded: On successful load
            error_occurred: On failure
        """
        pass

    @abstractmethod
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

        Args:
            pdf_data: PDF file contents as bytes
            filename: Name to display for the document
            page: Page number to open (1-indexed)
            zoom: Zoom level - named or numeric
            pagemode: Sidebar state
            nameddest: Named destination

        Emits:
            pdf_loaded: On successful load
            error_occurred: On failure
        """
        pass

    @abstractmethod
    def show_blank_page(self):
        """Show a blank page (no PDF loaded)."""
        pass

    @abstractmethod
    def print_pdf(self):
        """Trigger print for the current PDF.

        Emits:
            print_requested: For SYSTEM/QT_DIALOG handlers
            print_data_ready: For EMIT_SIGNAL handler
        """
        pass

    @abstractmethod
    def save_pdf(self):
        """Save the current PDF with annotations.

        Emits:
            save_requested: With PDF data and filename
            error_occurred: On failure
        """
        pass

    @abstractmethod
    def get_widget(self):
        """Get the Qt widget to display.

        Returns:
            QWidget: The widget containing the PDF viewer
        """
        pass

    @abstractmethod
    def cleanup(self):
        """Clean up resources before destruction.

        This method should:
        - Stop any ongoing JavaScript execution
        - Clear cached data
        - Release WebEngine resources
        - Prepare for safe deletion

        Called by PDFViewerWidget in closeEvent and destructor.
        """
        pass

    @abstractmethod
    def has_annotations(self) -> bool:
        """Check if the current PDF has annotations.

        Returns:
            bool: True if PDF has been annotated
        """
        pass

    @abstractmethod
    def get_page_count(self) -> int:
        """Get the total number of pages in the current PDF.

        Returns:
            int: Total page count, or 0 if no PDF loaded
        """
        pass

    @abstractmethod
    def get_current_page(self) -> int:
        """Get the current page number.

        Returns:
            int: Current page number (1-indexed), or 0 if no PDF loaded
        """
        pass


# Backend type registry (for future extensibility)
_backend_registry = {}


def register_backend(name: str, backend_class: type):
    """Register a backend implementation.

    Args:
        name: Backend name (e.g., "inprocess", "multiprocess")
        backend_class: Backend class (must inherit from ViewerBackend)
    """
    # Note: issubclass check disabled due to metaclass issues with QObject+ABC
    # Runtime will catch inheritance errors when methods are called
    _backend_registry[name] = backend_class


def get_backend(name: str) -> type:
    """Get a registered backend class.

    Args:
        name: Backend name

    Returns:
        Backend class

    Raises:
        KeyError: If backend not found
    """
    return _backend_registry[name]


def list_backends() -> list:
    """List all registered backend names.

    Returns:
        List of backend names
    """
    return list(_backend_registry.keys())
