"""PDF.js Viewer Widget for PySide6.

A production-ready, embeddable PDF viewer widget powered by Mozilla's PDF.js.
Supports viewing, annotating, saving, and printing PDFs with full feature control.
"""

__version__ = "1.1.2"

from .config import (
    ConfigPresets,
    PDFFeatures,
    PDFSecurityConfig,
    PDFViewerConfig,
    PrintHandler,
    validate_pdf_file,
)
from .print_manager import freeze_support
from .stability import configure_global_stability
from .widget import PDFViewerWidget

__all__ = [
    "PDFViewerWidget",
    "PDFViewerConfig",
    "PDFFeatures",
    "PDFSecurityConfig",
    "PrintHandler",
    "ConfigPresets",
    "validate_pdf_file",
    "configure_global_stability",
    "freeze_support",
]
