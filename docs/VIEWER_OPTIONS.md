# PDF.js Viewer Options

This document describes how to use viewer options to control how PDFs are displayed when loaded.

## Overview

PDF.js supports several URL parameters that control the initial state of the PDF viewer. The `pdfjs-viewer` packages expose these options through optional parameters on `load_pdf()` and `load_pdf_bytes()` methods.

## Supported Options

### 1. `page` - Initial Page Number

Opens the PDF at a specific page.

- **Type**: `int`
- **Range**: 1 to number of pages (1-indexed)
- **Example**: `page=5` opens the PDF at page 5

```python
# Open PDF at page 10
viewer.load_pdf("document.pdf", page=10)
```

### 2. `zoom` - Zoom Level

Controls the initial zoom level of the PDF.

- **Type**: `str` (named mode) or `int`/`float` (percentage)
- **Named modes**:
  - `"auto"` - Automatic zoom
  - `"page-width"` - Fit to page width
  - `"page-height"` - Fit to page height
  - `"page-fit"` - Fit entire page in view
- **Numeric mode**: Percentage from 10 to 1000
  - Example: `150` = 150% zoom

```python
# Named zoom modes
viewer.load_pdf("document.pdf", zoom="page-width")
viewer.load_pdf("document.pdf", zoom="page-fit")

# Numeric zoom (percentage)
viewer.load_pdf("document.pdf", zoom=150)  # 150% zoom
viewer.load_pdf("document.pdf", zoom=75)   # 75% zoom
```

### 3. `pagemode` - Sidebar State

Controls which sidebar panel is visible when the PDF loads.

- **Type**: `str`
- **Valid values**:
  - `"none"` - No sidebar visible (default)
  - `"thumbs"` - Show thumbnail sidebar
  - `"bookmarks"` - Show bookmarks/outline sidebar
  - `"attachments"` - Show attachments sidebar

```python
# Open with thumbnails sidebar
viewer.load_pdf("document.pdf", pagemode="thumbs")

# Open with bookmarks sidebar
viewer.load_pdf("document.pdf", pagemode="bookmarks")
```

### 4. `nameddest` - Named Destination

Jump to a named destination within the PDF (if the PDF defines named destinations).

- **Type**: `str`
- **Format**: Named destination string as defined in the PDF

```python
# Jump to named destination "chapter3"
viewer.load_pdf("document.pdf", nameddest="chapter3")
```

## Combining Options

You can combine multiple options together:

```python
# Open at page 5, with page-width zoom, and bookmarks visible
viewer.load_pdf(
    "document.pdf",
    page=5,
    zoom="page-width",
    pagemode="bookmarks"
)

# Open at page 10, 150% zoom, with thumbnails
viewer.load_pdf(
    "document.pdf",
    page=10,
    zoom=150,
    pagemode="thumbs"
)
```

## Using with Bytes

All options also work with `load_pdf_bytes()`:

```python
with open("document.pdf", "rb") as f:
    pdf_data = f.read()

viewer.load_pdf_bytes(
    pdf_data,
    filename="document.pdf",
    page=3,
    zoom="page-fit",
    pagemode="bookmarks"
)
```

## Backward Compatibility

All viewer options are optional parameters with default value `None`. Existing code that doesn't use these options continues to work unchanged:

```python
# Still works - loads with default settings
viewer.load_pdf("document.pdf")
viewer.load_pdf_bytes(pdf_data)
```

## Validation

The API validates all parameters and raises `ValueError` for invalid values:

```python
# Invalid page number
viewer.load_pdf("document.pdf", page=0)  # ValueError: Page number must be >= 1

# Invalid zoom mode
viewer.load_pdf("document.pdf", zoom="invalid")  # ValueError: Invalid zoom mode

# Invalid zoom percentage
viewer.load_pdf("document.pdf", zoom=5000)  # ValueError: Zoom percentage must be between 10 and 1000

# Invalid pagemode
viewer.load_pdf("document.pdf", pagemode="invalid")  # ValueError: Invalid pagemode
```

## Implementation Details

### How It Works

The viewer options are implemented using PDF.js's standard URL query parameter mechanism:

```
viewer.html?file=<path>&page=5&zoom=page-width&pagemode=bookmarks
```

The backend constructs the viewer URL with properly encoded query parameters using Qt's `QUrlQuery` class, ensuring correct URL encoding for all parameter values.

### Method Signatures

**PDFViewerWidget.load_pdf()**
```python
def load_pdf(
    self,
    source: Union[str, Path, bytes],
    page: Optional[int] = None,
    zoom: Optional[Union[str, int, float]] = None,
    pagemode: Optional[str] = None,
    nameddest: Optional[str] = None
) -> None
```

**PDFViewerWidget.load_pdf_bytes()**
```python
def load_pdf_bytes(
    self,
    data: bytes,
    filename: str = "document.pdf",
    page: Optional[int] = None,
    zoom: Optional[Union[str, int, float]] = None,
    pagemode: Optional[str] = None,
    nameddest: Optional[str] = None
) -> None
```

## Complete Example

```python
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow
from pdfjs_viewer import PDFViewerWidget, ConfigPresets

app = QApplication(sys.argv)
window = QMainWindow()
window.resize(1024, 768)

# Create viewer
viewer = PDFViewerWidget(config=ConfigPresets.unrestricted())
window.setCentralWidget(viewer)

# Load PDF with multiple options
viewer.load_pdf(
    "technical_manual.pdf",
    page=15,              # Open at page 15
    zoom="page-width",    # Fit to page width
    pagemode="bookmarks"  # Show bookmarks sidebar
)

window.show()
sys.exit(app.exec())
```

## Demo Application

See `examples/viewer_options.py` for a complete interactive demo that lets you experiment with all viewer options.

## PDF.js Documentation Reference

These options correspond to PDF.js viewer URL parameters:
- https://mozilla.github.io/pdf.js/
