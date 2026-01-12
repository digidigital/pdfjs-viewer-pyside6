"""PDF.js Viewer Widget for PySide6.

A production-ready, embeddable PDF viewer widget powered by Mozilla's PDF.js.
Supports viewing, annotating, saving, and printing PDFs with full feature control.
"""

__version__ = "1.0.0"

from .config import (
    ConfigPresets,
    PDFFeatures,
    PDFSecurityConfig,
    PDFStabilityConfig,
    PDFViewerConfig,
    PrintHandler,
    validate_pdf_file,
)
from .widget import PDFViewerWidget

__all__ = [
    "PDFViewerWidget",
    "PDFViewerConfig",
    "PDFFeatures",
    "PDFSecurityConfig",
    "PDFStabilityConfig",
    "PrintHandler",
    "ConfigPresets",
    "validate_pdf_file",
]
