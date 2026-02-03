# PDF.js Viewer Widget for PySide6

A production-ready, embeddable PDF viewer widget for PySide6 applications powered by Mozilla's PDF.js.

Visit [PDF.js Viewer for Qt](https://pdfjs-viewer.digidigital.de) homepage for more information.

Support the project: [Buy me a pizza!](https://buymeacoffee.com/digidigital) 👍

## Features

- 🖼️ **PDF.js Integration** - View, zoom, rotate, and navigate PDFs
- ✏️ **Annotations** - Highlight, draw, add text, stamps
- 💾 **Save with Annotations** - Export PDFs with baked-in annotations
- 🖨️ **Print Support** - Multiple print handlers (system, Qt dialog, custom)
- 🎨 **Theme Support** - Automatic light/dark mode following system preferences
- 📄 **Blank Page Support** - Show empty viewer with `show_blank_page()`
- ⚙️ **Viewer Options** - Control page, zoom, and sidebar when loading PDFs
- 🔒 **Security** - Suppress external links
- 🎛️ **Feature Control** - Enable/disable specific UI features
- 💾 **Unsaved Changes Protection** - Prompt, auto-save, or ignore unsaved annotations
- 🌍 **Localization** - 21+ languages for print and save dialogs
- 📦 **PyInstaller Ready** - Automatic bundling for frozen applications
- 🔧 **Customizable** - Use custom PDF.js versions
- 🌐 **Cross-Platform** - Works on Windows, macOS, and Linux

## Installation

```bash
pip install pdfjs-viewer-pyside6
```

## Quick Start

```python
from PySide6.QtWidgets import QApplication, QMainWindow
from pdfjs_viewer import PDFViewerWidget

app = QApplication([])
window = QMainWindow()
window.resize(1024, 768)

# Create viewer
viewer = PDFViewerWidget()
viewer.load_pdf("document.pdf")

# Or show blank page
# viewer.show_blank_page()

# Connect signals
viewer.pdf_loaded.connect(lambda meta: print(f"Loaded: {meta['filename']}"))
viewer.pdf_saved.connect(lambda data, path: print(f"Saved to {path}"))

window.setCentralWidget(viewer)
window.show()
app.exec()
```

## Viewer Options

Control how PDFs are displayed when loaded:

```python
# Open at specific page with custom zoom
viewer.load_pdf("document.pdf", page=5, zoom="page-width")

# Open with bookmarks sidebar visible
viewer.load_pdf("document.pdf", pagemode="bookmarks")

# Combine multiple options
viewer.load_pdf(
    "document.pdf",
    page=10,
    zoom=150,  # 150% zoom
    pagemode="thumbs"  # Show thumbnails
)
```

**Supported Options:**
- `page`: Page number to open (1-indexed)
- `zoom`: Zoom level - named (`"page-width"`, `"page-height"`, `"page-fit"`, `"auto"`) or numeric (10-1000)
- `pagemode`: Sidebar state - `"none"`, `"thumbs"`, `"bookmarks"`, or `"attachments"`
- `nameddest`: Named destination to navigate to

## Theme Support

The viewer automatically follows system theme preferences for light and dark mode.

### Theme Features

1. **Automatic Detection**: Follows system/application theme via CSS `prefers-color-scheme`
2. **Built-in Dark Mode**: PDF.js includes native dark mode styling that activates automatically
3. **No Configuration Needed**: Works out of the box

## Blank Page Display

Show an empty viewer without a PDF loaded:

```python
viewer.show_blank_page()
```

The blank page automatically follows the system theme.

## Configuration

### Disable Features

```python
from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig, PDFFeatures

features = PDFFeatures(
    print_enabled=True,
    save_enabled=True,
    load_enabled=False,      # Disable file loading
    presentation_mode=False,  # Disable presentation mode button
    stamp_enabled=False,      # Disable stamp annotations
)

config = PDFViewerConfig(features=features)
viewer = PDFViewerWidget(config=config)
```

### Security Settings

```python
from pdfjs_viewer import PDFSecurityConfig

security = PDFSecurityConfig(
    allow_external_links=False,   # Block external URLs
    block_remote_content=True,    # Block remote resources
)

config = PDFViewerConfig(security=security)
viewer = PDFViewerWidget(config=config)
```

### Custom PDF.js

You can initialize the widget with a customized version of PDF.js
```python
viewer = PDFViewerWidget(
    pdfjs_path="/path/to/custom/pdfjs-5.5.0-dist"
)
```
This "should" work fine for minor releases or cosmetic changes and will most likely break for major releases.

## API Reference

### PDFViewerWidget

Main widget class for viewing PDFs.

#### Methods

- `load_pdf(source: str | Path | bytes)` - Load PDF from file path or bytes
- `show_blank_page()` - Show empty viewer (respects current theme)
- `save_pdf(output_path: str = None) -> bytes` - Save PDF with annotations
- `print_pdf()` - Trigger print dialog
- `get_pdf_data() -> bytes` - Get current PDF data with annotations
- `has_annotations() -> bool` - Check if PDF has been annotated
- `has_unsaved_changes() -> bool` - Check if document has unsaved annotations
- `handle_unsaved_changes() -> bool` - Handle unsaved changes per config
- `goto_page(page: int)` - Navigate to specific page
- `get_page_count() -> int` - Get total page count
- `get_current_page() -> int` - Get current page number
- `set_features_enabled(features: PDFFeatures)` - Update feature flags

#### Signals

All signals developers can listen to:

- `pdf_loaded(metadata: dict)` - Emitted when PDF successfully loads. Metadata includes filename, page count, and other PDF information.
- `pdf_saved(data: bytes, path: str)` - Emitted when PDF is saved. Provides PDF data with baked-in annotations and the save path.
- `print_requested(data: bytes)` - Emitted when print is triggered using SYSTEM or QT_DIALOG handlers. Contains PDF data ready for printing.
- `print_data_ready(data: bytes, filename: str)` - Emitted when using EMIT_SIGNAL print handler. Provides PDF data and original filename for custom print handling.
- `annotation_modified()` - Emitted when annotations are added, changed, or removed.
- `page_changed(current: int, total: int)` - Emitted when current page changes. Provides current page number and total page count.
- `error_occurred(message: str)` - Emitted when errors occur during PDF operations.
- `external_link_blocked(url: str)` - Emitted when an external link is blocked by security settings.

### Configuration Classes

> **Note:** The default values shown below are the **class defaults** used when you instantiate these classes directly. When using `PDFViewerWidget()` without explicit configuration, the **annotation preset** is applied instead—see [Configuration Presets](#configuration-presets) for the actual default values.
>
> **Recommendation:** For most use cases, use the [hybrid approach](#method-2-hybrid-approach-recommended) documented under Configuration Presets. Start with a preset and modify only the settings you need. Working with these configuration classes directly is mainly useful for development or special cases.

#### PDFFeatures

Controls which UI features are enabled.

```python
PDFFeatures(
    # Core actions
    print_enabled: bool = True,
    save_enabled: bool = True,
    load_enabled: bool = True,
    presentation_mode: bool = False,

    # Annotation tools
    highlight_enabled: bool = True,
    freetext_enabled: bool = True,
    ink_enabled: bool = True,
    stamp_enabled: bool = True,
    stamp_alttext_enabled: bool = True,  # Enable alt-text dialog for stamps

    # Navigation
    bookmark_enabled: bool = False,
    scroll_mode_buttons: bool = True,
    spread_mode_buttons: bool = True,

    # Unsaved changes behavior
    unsaved_changes_action: str = "disabled",  # "disabled", "prompt", "auto_save"
)
```

#### PDFSecurityConfig

Security and privacy settings.

```python
PDFSecurityConfig(
    allow_external_links: bool = False,
    confirm_before_external_link: bool = True,  # Show confirmation dialog before opening
    block_remote_content: bool = True,
    allowed_protocols: List[str] = ["http", "https"],
    custom_csp: str = None,  # Optional custom Content Security Policy
)
```

#### PDFViewerConfig

Main configuration container.

```python
PDFViewerConfig(
    features: PDFFeatures = PDFFeatures(),
    security: PDFSecurityConfig = PDFSecurityConfig(),

    # Behavior
    auto_open_folder_on_save: bool = True,
    disable_context_menu: bool = True,

    # Print handling
    print_handler: PrintHandler = PrintHandler.SYSTEM,
    print_dpi: int = 300,
    print_fit_to_page: bool = True,

    # PDF.js settings
    default_zoom: str = "auto",
    sidebar_visible: bool = False,
    spread_mode: str = "none",  # "none", "odd", "even"
)
```

## Print Handling

The viewer supports multiple print handling modes to fit different application needs. Configure via the `print_handler` setting in `PDFViewerConfig`.

### Print Handler Modes

#### SYSTEM (Default)
Opens PDF with system default viewer for printing. Simple and reliable.

```python
from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig, PrintHandler

config = PDFViewerConfig(print_handler=PrintHandler.SYSTEM)
viewer = PDFViewerWidget(config=config)

# Listen to print_requested signal
viewer.print_requested.connect(lambda data: print(f"Opening {len(data)} bytes in system viewer"))
```

**Best for:**
- Simple applications
- Delegating to OS print dialog
- Maximum compatibility

#### QT_DIALOG
Uses a basic Qt print dialog with pypdfium2 for PDF rendering. Requires pypdfium2 package.

```python
config = PDFViewerConfig(
    print_handler=PrintHandler.QT_DIALOG,
    print_dpi=300,              # DPI for rendering (default: 300)
    print_fit_to_page=True      # Scale to fit page (default: True)
)
viewer = PDFViewerWidget(config=config)

# Listen to print_requested signal
viewer.print_requested.connect(lambda data: print("Qt print dialog opening"))
```

**Best for:**
- Embedded printing without external apps
- Custom print settings UI
- Direct printer access

**Requirements:**
```bash
pip install pypdfium2
```

#### EMIT_SIGNAL
Emits signal with PDF data for completely custom handling. No built-in printing.

```python
config = PDFViewerConfig(print_handler=PrintHandler.EMIT_SIGNAL)
viewer = PDFViewerWidget(config=config)

# Listen to print_data_ready signal (NOT print_requested)
def handle_print(pdf_data: bytes, filename: str):
    print(f"Custom print handling for {filename}")
    # Send to print server, save to queue, etc.

viewer.print_data_ready.connect(handle_print)
```

**Best for:**
- Server-side printing
- Print queue systems
- Custom print workflows
- Cloud printing services

### Print Handler Comparison

| Mode | Signal | Requires pypdfium2 | Use Case |
|------|--------|-------------------|----------|
| SYSTEM | `print_requested(bytes)` | No | Simple, OS-based printing |
| QT_DIALOG | `print_requested(bytes)` | Yes | Embedded Qt print dialog |
| EMIT_SIGNAL | `print_data_ready(bytes, str)` | No | Custom print handling |

### Print Configuration Options

Additional settings available for `QT_DIALOG` mode:

```python
config = PDFViewerConfig(
    print_handler=PrintHandler.QT_DIALOG,
    print_dpi=300,              # Rendering DPI (default: 300)
    print_fit_to_page=True      # Scale to fit vs actual size (default: True)
)
```

## Configuration Presets

The package provides 7 pre-configured presets for common use cases. You can use them as-is or customize them for your specific needs.

### Available Presets

```python
from pdfjs_viewer import PDFViewerWidget, ConfigPresets

# List all available presets
print(ConfigPresets.list())
# ['readonly', 'simple', 'annotation', 'form', 'kiosk', 'safer', 'unrestricted']
```

#### 1. readonly - View-Only Mode
Maximum security, no editing capabilities.

```python
viewer = PDFViewerWidget(preset="readonly")
```

**Features:** No printing, no saving, no annotations, no external links
**Best for:** Kiosk displays, untrusted PDFs, embedded viewing

#### 2. simple - Basic Viewer
Standard PDF viewing with print/save.

```python
viewer = PDFViewerWidget(preset="simple")
```

**Features:** Print, save, basic annotations (highlight, text)
**Best for:** General PDF viewing, most common use case

#### 3. annotation - Full Editing (Default)
All annotation and editing tools enabled. **This is the default preset when no configuration is specified.**

```python
viewer = PDFViewerWidget(preset="annotation")
# or simply
viewer = PDFViewerWidget()  # annotation is the default
```

**Features:** All annotation tools, file loading, external links
**Best for:** PDF review, collaborative annotation, document workflows

#### 4. form - Form Filling
Optimized for PDF form completion.

```python
viewer = PDFViewerWidget(preset="form")
```

**Features:** Text input, signatures, no external links
**Best for:** Government forms, insurance applications, contract signing

#### 5. kiosk - Public Terminal
For 24/7 public displays.

```python
viewer = PDFViewerWidget(preset="kiosk")
```

**Features:** Print only, no saving/editing, maximum stability
**Best for:** Libraries, museums, public information terminals

#### 6. safer - Maximum Stability
For crash-prone or embedded systems.

```python
viewer = PDFViewerWidget(preset="safer")
```

**Features:** Minimal features, all stability options enabled, basic viewing
**Best for:** Embedded Linux, older Qt versions, mission-critical apps

#### 7. unrestricted - Full PDF.js
No restrictions, all features enabled.

```python
viewer = PDFViewerWidget(preset="unrestricted")
```

**Features:** Everything enabled, developer-friendly
**Best for:** Development, testing, fully trusted PDFs

### Customizing Presets

There are three ways to customize presets to fine-tune behavior for your application:

#### Method 1: Simple Customization (Quick Override)

Use the `customize` parameter for simple property changes:

```python
# Start with readonly, but enable saving
viewer = PDFViewerWidget(
    preset="readonly",
    customize={
        "features": {"save_enabled": True}
    }
)

# Start with simple, but use Qt print dialog
viewer = PDFViewerWidget(
    preset="simple",
    customize={
        "print_handler": PrintHandler.QT_DIALOG,
        "features": {"ink_enabled": True}
    }
)
```

#### Method 2: Hybrid Approach (Recommended)

Get preset config, modify it, then pass to widget:

```python
from pdfjs_viewer import PDFViewerWidget, ConfigPresets, PrintHandler

# Start with annotation preset
config = ConfigPresets.annotation()

# Fine-tune specific settings
config.print_handler = PrintHandler.EMIT_SIGNAL
config.features.stamp_enabled = False
config.security.allow_external_links = False

# Create viewer with customized config
viewer = PDFViewerWidget(config=config)
```

This approach gives you:
- IDE autocomplete for settings
- Type checking
- Clear, readable code
- Full control over configuration

#### Method 3: Custom Preset Builder

Use `ConfigPresets.custom()` for complex customizations:

```python
from pdfjs_viewer import ConfigPresets, PrintHandler

config = ConfigPresets.custom(
    base="simple",
    features={
        "ink_enabled": True,
        "stamp_enabled": True,
    },
    security={
        "allow_external_links": False,
    },
    print_handler=PrintHandler.QT_DIALOG,
    print_dpi=600,
)

viewer = PDFViewerWidget(config=config)
```

### Fine-Tuning Examples

#### Example 1: Readonly + Save Only

Allow users to view and save PDFs, but not edit:

```python
config = ConfigPresets.readonly()
config.features.save_enabled = True
viewer = PDFViewerWidget(config=config)
```

#### Example 2: Annotation with Custom Print

Full annotation tools but with custom print handling:

```python
config = ConfigPresets.annotation()
config.print_handler = PrintHandler.EMIT_SIGNAL

viewer = PDFViewerWidget(config=config)
viewer.print_data_ready.connect(my_custom_print_handler)
```

#### Example 3: Custom Feature Mix

Cherry-pick features from different presets:

```python
from pdfjs_viewer import PDFViewerConfig, PDFFeatures, PDFSecurityConfig

config = PDFViewerConfig(
    features=PDFFeatures(
        print_enabled=True,
        save_enabled=True,
        highlight_enabled=True,
        ink_enabled=True,
        stamp_enabled=False,  
    ),
    security=PDFSecurityConfig(
        allow_external_links=True,
        block_remote_content=True,
    ),
    print_handler=PrintHandler.QT_DIALOG,
)

viewer = PDFViewerWidget(config=config)
```

### Preset Configuration Reference

Each preset configures two main areas:

1. **Features** (`PDFFeatures`) - Which UI elements are enabled
2. **Security** (`PDFSecurityConfig`) - Link and content policies

See [Configuration Classes](#configuration-classes) section above for full details on available settings.

## Unsaved Changes Handling

The viewer can be configured to handle unsaved annotations when:
- Closing the viewer
- Loading a new PDF
- Navigating away from the current document

### Configuration

Set the `unsaved_changes_action` in `PDFFeatures`:

```python
from pdfjs_viewer import PDFViewerWidget, ConfigPresets

# Method 1: Using preset with customize
viewer = PDFViewerWidget(
    preset="annotation",
    customize={"features": {"unsaved_changes_action": "prompt"}}
)

# Method 2: Modify config directly
config = ConfigPresets.annotation()
config.features.unsaved_changes_action = "prompt"
viewer = PDFViewerWidget(config=config)
```

### Available Modes

| Mode | Description | Behavior |
|------|-------------|----------|
| `"disabled"` | No warning (default) | Changes may be lost without prompting |
| `"prompt"` | Show dialog | User chooses: Save As / Save / Discard |
| `"auto_save"` | Auto-save | Automatically saves to original file |

### Dialog Options (prompt mode)

When `unsaved_changes_action="prompt"`, a dialog appears with three options:

- **Save As...** - Opens file picker to choose save location
- **Save** - Overwrites the original PDF file with annotations
- **Discard** - Discards changes and continues without saving

### Preset Defaults

| Preset | Default Action |
|--------|---------------|
| `readonly` | `disabled` (no editing possible) |
| `simple` | `prompt` |
| `annotation` | `prompt` |
| `form` | `prompt` |
| `kiosk` | `disabled` (no user interaction) |
| `safer` | `prompt` |
| `unrestricted` | `disabled` (backwards compatible) |

### Programmatic Checking

You can check and handle unsaved changes programmatically:

```python
# Check if there are unsaved changes
if viewer.has_unsaved_changes():
    print("Document has unsaved annotations")

# Handle unsaved changes according to config
# Returns True if safe to proceed, False if user cancelled Save As
if viewer.handle_unsaved_changes():
    # Safe to close or navigate
    pass
```

### Translations

The dialog is translated in 21 languages, matching the print dialog translations.

## Global Stability Settings

For maximum stability, configure WebEngine settings **before** creating QApplication:

```python
from pdfjs_viewer.stability import configure_global_stability

# Call BEFORE QApplication creation
configure_global_stability(
    disable_gpu=True,
    disable_webgl=True,
    disable_gpu_compositing=True,
    disable_unnecessary_features=True,
)

# Then create your application
app = QApplication(sys.argv)
```

## Utility Functions

### validate_pdf_file

Check if a file is actually a PDF before loading:

```python
from pdfjs_viewer import validate_pdf_file

if validate_pdf_file("/path/to/file.pdf"):
    viewer.load_pdf("/path/to/file.pdf")
else:
    print("Not a valid PDF file")
```

## Examples

See [examples/](https://github.com/digidigital/pdfjs-viewer-pyside6/examples/) directory for complete examples:

- [basic_viewer.py](https://github.com/digidigital/pdfjs-viewer-pyside6/examples/basic_viewer.py) - Simple PDF viewer
- [feature_control.py](https://github.com/digidigital/pdfjs-viewer-pyside6/examples/feature_control.py) - Static feature configuration
- [feature_selection.py](https://github.com/digidigital/pdfjs-viewer-pyside6/examples/feature_selection.py) - Interactive feature demo
- [print_handlers.py](https://github.com/digidigital/pdfjs-viewer-pyside6/examples/print_handlers.py) - All print handler modes
- [unsaved_changes_demo.py](https://github.com/digidigital/pdfjs-viewer-pyside6/examples/unsaved_changes_demo.py) - Unsaved changes handling
- [external_link_handler.py](https://github.com/digidigital/pdfjs-viewer-pyside6/examples/external_link_handler.py) - Link security handling
- [viewer_options.py](https://github.com/digidigital/pdfjs-viewer-pyside6/examples/viewer_options.py) - Page, zoom, sidebar options

## PyInstaller Support

PDF.js files are automatically bundled when freezing your application.
A hook automatically includes all required PDF.js files and templates.

**Directory structure** (PyInstaller >= 5.0):
```
dist/your_app/
├── your_app.exe          # Executable
└── _internal/            # All resources
    └── pdfjs_viewer/     # Automatically included
```

## Requirements

- Python >= 3.10
- PySide6 >= 6.10.0 (excluding 6.10.1 due to a bug)
- PySide6-Addons >= 6.10.0
- PySide6-Essentials >= 6.10.0
- pypdfium2
- Pillow
- pikepdf

## PDF.js Version

This package bundles PDF.js version **5.4.530** (Apache License 2.0).

## License

This package is licensed under the **GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later)**.

See [LICENSE](https://github.com/digidigital/pdfjs-viewer-pyside6/LICENSE) for the full license text.

### PySide6 LGPL Notice

This module uses **PySide6 (Qt for Python), licensed under the LGPL v3**.

**Important for application developers:**
- You may use this module in proprietary applications
- PySide6 and Qt libraries must remain as external shared libraries (not statically linked)
- Users must be able to replace the PySide6/Qt libraries
- See [LICENSE_NOTICE.md](https://github.com/digidigital/pdfjs-viewer-pyside6/LICENSE_NOTICE.md) for full compliance details

### Bundled Dependencies

- **PDF.js** - Apache License 2.0 (see `src/pdfjs_viewer/pdfjs/LICENSE`)

### Library Replacement

When distributing frozen applications (e.g., with PyInstaller), PySide6 and Qt libraries are kept as external shared libraries in the `_internal` directory, allowing users to replace them as required by the LGPL.

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

## Support

- **Issues**: [GitHub Issues](https://github.com/digidigital/pdfjs-viewer-pyside6/issues)
- **Documentation**: Full API documentation available in source code

## Changelog

### v1.1.0 (2026-02-02)

#### New Features
- **Unsaved Changes Protection**: New `unsaved_changes_action` setting with three modes:
  - `"disabled"` - No prompts (default, backwards compatible)
  - `"prompt"` - Dialog with Save As / Save / Discard options
  - `"auto_save"` - Automatic save before navigation
- **Global Stability Configuration**: New `stability.configure_global_stability()` for crash prevention
- **PDF Validation**: New `validate_pdf_file()` utility function
- **Stamp Alt-Text Control**: New `stamp_alttext_enabled` to disable alt-text dialog
- **View Mode Controls**: New `scroll_mode_buttons` and `spread_mode_buttons` features
- **Bookmark Toggle**: New `bookmark_enabled` feature flag
- **Separate Process Printing**: Print dialog now runs in isolated process for stability

#### Improvements
- Sequential PDF page rendering for better memory management
- Print dialog translations in 21+ languages
- Unsaved changes dialog translations in 21+ languages
- Improved home directory detection for Snap packages
- Better error handling with specific exception types
- Resource cleanup with context managers

#### Breaking Changes
- `PDFStabilityConfig` removed — safe defaults are now always applied internally. Use `configure_global_stability()` for Chromium flags.
- `confirm_before_external_link` moved from `PDFViewerConfig` to `PDFSecurityConfig`
- `print_parallel_pages` is deprecated and ignored (printing is now sequential)
- `signature_enabled` and `comment_enabled` removed (not exposed in PDF.js UI)
- `presentation_mode` now defaults to `False`
- `allow_javascript` and `sandbox_enabled` removed from `PDFSecurityConfig` (controlled globally)

#### Bug Fixes
- Fixed memory leaks in PDF rendering
- Fixed bare except clauses throughout codebase
- Fixed resource leaks with pikepdf
- Fixed subprocess error handling for system PDF viewer

### v1.0.0 (2026-01-12)

- Initial release
- PDF.js 5.4.530 integration
- Annotation support (highlight, text, ink, stamp)
- Save/print with annotations
- Light/dark mode synchronization
- `show_blank_page()` function for empty viewer
- Configurable feature control
- Security settings and sandbox
- PyInstaller support (>= 5.0 with `_internal` directory)
