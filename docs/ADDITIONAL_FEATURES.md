# Additional Features Guide

This document describes additional features and capabilities of the PDF viewer beyond basic PDF display.

## Table of Contents

1. [Save Dialog Location Memory](#save-dialog-location-memory)
2. [External Link Handling](#external-link-handling)
3. [Generic Document Viewer](#generic-document-viewer)

---

## Save Dialog Location Memory

### Feature Description

When you load a PDF from a specific directory and then click the save button in PDF.js, the Qt save dialog now automatically opens in the same directory where the PDF was loaded from.

### Implementation

**Automatic:** This feature works automatically with no configuration needed.

**How it works:**
1. When `load_pdf(file_path)` is called, the directory is tracked internally
2. When user clicks save in PDF.js, the save dialog opens at: `<original_directory>/<filename>`
3. For PDFs loaded from bytes (`load_pdf_bytes()`), the save dialog opens at the current directory

### Example

```python
from pdfjs_viewer import PDFViewerWidget

viewer = PDFViewerWidget()

# Load PDF from /home/user/documents/report.pdf
viewer.load_pdf("/home/user/documents/report.pdf")

# User clicks save button in PDF.js
# Save dialog opens at: /home/user/documents/report_annotated.pdf
#                        ^^^^^^^^^^^^^^^^^^^^^^^^^ same directory!
```

### Benefits

- **Better UX:** Users expect to save near the source file
- **Reduces clicks:** No need to navigate to the original folder
- **Intuitive:** Matches behavior of most desktop applications

### Technical Details

**Location:** [backend_inprocess.py:696-700](src/pdfjs_viewer/backend_inprocess.py#L696-L700)

The `_current_pdf_directory` attribute tracks the directory:
- Set in `load_pdf()` when loading from file path
- Cleared when loading from bytes
- Used in `_on_save_requested()` to construct initial save path

---

## External Link Handling

### Feature Description

The viewer provides comprehensive control over how external links (http/https URLs) in PDFs are handled, including:
- Detecting when links are clicked
- Blocking links for security
- Custom handling strategies
- User prompts before opening links

### Signal: `external_link_blocked`

Emitted when a user clicks an external link that is blocked by security settings.

**Signature:**
```python
external_link_blocked = Signal(str)  # url parameter
```

**When emitted:**
- User clicks http/https link in PDF
- `allow_external_links=False` in security config
- Not emitted for internal PDF links (page navigation)

### Configuration

External links are controlled via `PDFSecurityConfig`:

```python
from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig, PDFSecurityConfig

config = PDFViewerConfig(
    security=PDFSecurityConfig(
        allow_external_links=False,  # Block external links
        block_remote_content=True,   # Also block remote resources
    )
)

viewer = PDFViewerWidget(config=config)
```

### Handling Strategies

#### 1. Block All Links (Security)

**Use case:** Production environments, untrusted PDFs, security-critical applications

```python
config = PDFViewerConfig(
    security=PDFSecurityConfig(
        allow_external_links=False,
        block_remote_content=True,
    )
)

viewer = PDFViewerWidget(config=config)

# Log blocked links
viewer.external_link_blocked.connect(
    lambda url: print(f"Blocked: {url}")
)
```

#### 2. Ask User Before Opening (Flexible)

**Use case:** Desktop applications where user should control link opening

```python
from PySide6.QtWidgets import QMessageBox
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

config = PDFViewerConfig(
    security=PDFSecurityConfig(
        allow_external_links=False,  # Block, but we'll handle manually
    )
)

viewer = PDFViewerWidget(config=config)

def ask_before_opening(url: str):
    reply = QMessageBox.question(
        parent_widget,
        "External Link",
        f"Open link in browser?\\n\\n{url}",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )

    if reply == QMessageBox.StandardButton.Yes:
        QDesktopServices.openUrl(QUrl(url))

viewer.external_link_blocked.connect(ask_before_opening)
```

#### 3. Allow All Links (Convenient)

**Use case:** Trusted PDFs, documentation viewers, internal tools

```python
config = PDFViewerConfig(
    security=PDFSecurityConfig(
        allow_external_links=True,  # Links open automatically
    )
)

viewer = PDFViewerWidget(config=config)
# Links open in external browser automatically
```

#### 4. Whitelist Specific Domains

**Use case:** Allow links to trusted domains only

```python
ALLOWED_DOMAINS = ["example.com", "docs.python.org", "github.com"]

config = PDFViewerConfig(
    security=PDFSecurityConfig(
        allow_external_links=False,
    )
)

viewer = PDFViewerWidget(config=config)

def check_whitelist(url: str):
    from urllib.parse import urlparse
    domain = urlparse(url).netloc

    if any(allowed in domain for allowed in ALLOWED_DOMAINS):
        print(f"Allowed domain: {url}")
        QDesktopServices.openUrl(QUrl(url))
    else:
        print(f"Blocked domain: {url}")

viewer.external_link_blocked.connect(check_whitelist)
```

### Important Notes

**Internal Links Always Work:**
Navigation links within the PDF (page jumps, bookmarks) always work regardless of external link settings.

**Security Considerations:**
- **Phishing:** PDFs can contain malicious links
- **Privacy:** External links may track users
- **Best Practice:** Block by default, allow explicitly

### Examples

See comprehensive examples in:
- [examples/external_link_handler.py](examples/external_link_handler.py) - Interactive demo with multiple strategies
- [examples/feature_control.py](examples/feature_control.py) - Basic blocking example

---

## Generic Document Viewer

### Feature Description

The PDF viewer's underlying `QWebEngineView` can be reused to display various document types beyond PDFs, making it useful for applications that need to preview multiple formats.

### Supported Formats

The viewer natively supports:

| Format | Extensions | Display Method |
|--------|-----------|----------------|
| **PDF** | `.pdf` | PDF.js (full features) |
| **HTML** | `.html`, `.htm` | Native browser rendering |
| **XML** | `.xml` | Browser XML viewer |
| **Text** | `.txt`, `.md`, `.log` | Plain text display |
| **Images** | `.png`, `.jpg`, `.gif`, `.svg`, `.bmp` | Native image rendering |

### Usage

#### Method 1: Using load_pdf() for PDFs

```python
from pdfjs_viewer import PDFViewerWidget

viewer = PDFViewerWidget()

# PDF files use PDF.js (annotations, printing, etc.)
viewer.load_pdf("document.pdf")
```

#### Method 2: Using QWebEngineView directly for other formats

```python
from PySide6.QtCore import QUrl
from pathlib import Path

viewer = PDFViewerWidget()

# Access underlying web view
web_view = viewer.backend.web_view

# Load HTML file
html_path = Path("document.html").absolute()
web_view.setUrl(QUrl.fromLocalFile(str(html_path)))

# Or set HTML content directly
web_view.setHtml("<h1>Hello World</h1>", QUrl("file:///"))
```

### Complete Example

```python
from PySide6.QtCore import QUrl
from pathlib import Path
from pdfjs_viewer import PDFViewerWidget

viewer = PDFViewerWidget()
web_view = viewer.backend.web_view

def load_document(file_path: str):
    """Load any supported document type."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == '.pdf':
        # Use PDF.js for PDFs
        viewer.load_pdf(file_path)
    else:
        # Use QWebEngineView for other formats
        url = QUrl.fromLocalFile(str(path.absolute()))
        web_view.setUrl(url)

# Load various formats
load_document("report.pdf")      # PDF with annotations
load_document("page.html")       # HTML with CSS
load_document("config.xml")      # XML structure
load_document("readme.txt")      # Plain text
load_document("diagram.png")     # Image
```

### Use Cases

1. **Multi-format document preview:**
   ```python
   # Application that previews various file types
   def preview_file(path):
       if path.endswith('.pdf'):
           viewer.load_pdf(path)
       else:
           viewer.backend.web_view.setUrl(QUrl.fromLocalFile(path))
   ```

2. **Documentation viewer:**
   ```python
   # Display HTML docs and PDF manuals in same viewer
   def show_help(topic):
       if topic.is_pdf:
           viewer.load_pdf(topic.pdf_path)
       else:
           viewer.backend.web_view.setHtml(topic.html_content)
   ```

3. **Log file viewer:**
   ```python
   # Display text logs with formatting
   def show_log(log_path):
       with open(log_path) as f:
           content = f.read()

       html = f"<pre style='font-family: monospace;'>{escape(content)}</pre>"
       viewer.backend.web_view.setHtml(html)
   ```

### Important Notes

**Switching Between Formats:**
You can freely switch between PDF and other formats:
```python
viewer.load_pdf("document.pdf")           # PDF mode
viewer.backend.web_view.setHtml("<h1>Test</h1>")  # HTML mode
viewer.load_pdf("another.pdf")            # Back to PDF mode
```

**Profile Isolation Still Active:**
The security and stability settings apply to all formats:
- Profile isolation
- JavaScript settings
- Cache control
- External link blocking

**PDF.js Features Only for PDFs:**
When using `setUrl()` or `setHtml()` for non-PDF content:
- ✅ Display works normally
- ❌ PDF.js features unavailable (annotations, etc.)
- ❌ PDF-specific signals not emitted

### Examples

See comprehensive example:
- [examples/generic_document_viewer.py](examples/generic_document_viewer.py) - Multi-format viewer with samples

---

## Summary

| Feature | Configuration | Signal | Example |
|---------|--------------|---------|---------|
| **Save Location** | Automatic | None | N/A |
| **External Links** | `allow_external_links` | `external_link_blocked` | [external_link_handler.py](examples/external_link_handler.py) |
| **Generic Viewer** | Access `backend.web_view` | None | [generic_document_viewer.py](examples/generic_document_viewer.py) |

---

## API Reference

### Signals

```python
class PDFViewerWidget:
    # External link handling
    external_link_blocked = Signal(str)  # Emitted when external link is blocked
```

### Configuration

```python
@dataclass
class PDFSecurityConfig:
    allow_external_links: bool = False  # Allow http/https links
    block_remote_content: bool = True   # Block remote resources
```

### Methods

```python
class PDFViewerWidget:
    def load_pdf(self, file_path: str):
        """Load PDF (tracks directory for save dialog)."""

    def load_pdf_bytes(self, data: bytes, filename: str = "document.pdf"):
        """Load PDF from bytes (no directory tracking)."""

# Access underlying web view for generic documents
viewer.backend.web_view.setUrl(QUrl)
viewer.backend.web_view.setHtml(str, QUrl)
```

---

## Testing

All features have been tested:

```bash
# Test save dialog location
python examples/basic_viewer.py  # Load PDF, click save

# Test external link handling
python examples/external_link_handler.py

# Test generic document viewing
python examples/generic_document_viewer.py
```

---

## Migration Notes

**No Breaking Changes:**
All features are backward compatible. Existing code continues to work without modification.

**New Capabilities:**
- Save dialog automatically uses source directory
- External link blocking signal available for custom handling
- Generic document display possible via `backend.web_view`

---

## Future Enhancements

Potential future additions:
- [ ] Save location preference persistence
- [ ] Domain whitelist configuration in PDFSecurityConfig
- [ ] Markdown rendering helper
- [ ] Document format auto-detection
- [ ] Print support for non-PDF documents

---

*Last updated: 2026-01-09*
