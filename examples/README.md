# PDF.js Viewer Examples

This directory contains examples demonstrating various features and use cases of the `pdfjs-viewer-pyside6` package.

Support the project: [Buy me a pizza!](https://buymeacoffee.com/digidigital) 👍

## Quick Start Examples

### [basic_viewer.py](basic_viewer.py)
**Simplest possible PDF viewer** - Just 15 lines of code!
- Perfect starting point for beginners
- Shows minimal configuration needed
- Demonstrates loading a PDF file

### [debug_viewer.py](debug_viewer.py)
**Development and debugging example**
- Enables JavaScript console logging
- Useful for troubleshooting PDF.js issues
- Shows how to monitor PDF.js events

## Feature Configuration

### [feature_control.py](feature_control.py)
**Static feature configuration example**
- Simple, straightforward code showing how to disable UI features
- Demonstrates PDFFeatures and PDFSecurityConfig
- Good for understanding basic configuration options
- Use this as a template when you know which features to enable/disable

### [feature_selection.py](feature_selection.py)
**Interactive feature demo**
- Full-featured demo with checkboxes to toggle all features
- Shows ALL available PDFFeatures configuration options
- Allows runtime reload with different feature sets
- Great for exploring what each feature does
- Use this to determine which features you want for your app

**Key Difference**: `feature_control.py` is a minimal code example, while `feature_selection.py` is an interactive playground to test all features.

### [disable_stamp_alttext.py](disable_stamp_alttext.py)
**Disable stamp alt-text feature**
- Shows how to disable the alt-text dialog for stamp annotations
- Useful if you find the alt-text feature intrusive
- Demonstrates advanced PDF.js customization

## Print Handlers

### [print_handlers.py](print_handlers.py)
**Comprehensive print handler demonstration**
- Shows all three print handler options (SYSTEM, QT_DIALOG, EMIT_SIGNAL)
- Interactive demo to switch between handlers at runtime
- Demonstrates custom print workflows
- **Essential reading** if you need printing functionality

Print handler options:
- **SYSTEM**: Opens PDF in system default viewer (simple, reliable)
- **QT_DIALOG**: Shows Qt print dialog with page selection (requires pypdfium2)
- **EMIT_SIGNAL**: Emits signal for custom print handling (maximum flexibility)

## Security & Link Handling

### [external_link_handler.py](external_link_handler.py)
**External link security and handling**
- Demonstrates blocking/allowing external links
- Shows how to intercept and handle link clicks
- Custom URL validation and user confirmation dialogs

## Unsaved Changes Handling

### [unsaved_changes_demo.py](unsaved_changes_demo.py)
**Unsaved changes protection demo**
- Shows all three modes: disabled, prompt, auto_save
- Interactive mode switching
- Demonstrates `has_unsaved_changes()` and `handle_unsaved_changes()` methods
- **Essential for production applications**

## Viewer Options

### [viewer_options.py](viewer_options.py)
**PDF loading options demo**
- Open at specific page
- Set zoom level (named or percentage)
- Control sidebar visibility (pagemode)
- Navigate to named destinations

## Document Viewer Patterns

### [generic_document_viewer.py](generic_document_viewer.py)
**Multi-format document viewer**
- Demonstrates reusing QWebEngineView for HTML, XML, text, images
- Shows how to switch between PDF.js and direct web rendering
- Example of a versatile document preview application

## Running the Examples

All examples can be run directly:

```bash
python basic_viewer.py
python feature_selection.py
python print_handlers.py
# etc.
```

Some examples expect PDF files. You can:
1. Modify the code to point to your PDF file
2. Use the file dialog to open a PDF
3. Start with a blank viewer and use the Load button

## Which Example Should I Use?

- **Just getting started?** → `basic_viewer.py`
- **Want to explore features?** → `feature_selection.py`
- **Need to understand a specific feature?** → `feature_control.py` (as template)
- **Need printing?** → `print_handlers.py`
- **Need unsaved changes protection?** → `unsaved_changes_demo.py`
- **Need page/zoom control?** → `viewer_options.py`
- **Building a document viewer app?** → `generic_document_viewer.py`
- **Dealing with external links?** → `external_link_handler.py`

## Development Tips

1. Start with `basic_viewer.py` to understand the basics
2. Use `feature_selection.py` to explore all features interactively
3. Copy `feature_control.py` as a template for your own app
4. Read `print_handlers.py` carefully if you need printing
5. Use `debug_viewer.py` when troubleshooting

## Common Patterns

### Loading a PDF

```python
from pdfjs_viewer import PDFViewerWidget

viewer = PDFViewerWidget()
viewer.load_pdf("/path/to/document.pdf")
```

### Configuring Features

```python
from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig, PDFFeatures

config = PDFViewerConfig(
    features=PDFFeatures(
        print_enabled=True,
        save_enabled=False,  # Disable save button
        stamp_enabled=False  # Disable stamp annotations
    )
)
viewer = PDFViewerWidget(config=config)
```

### Handling Signals

```python
viewer.pdf_loaded.connect(lambda meta: print(f"Loaded: {meta['filename']}"))
viewer.pdf_saved.connect(lambda data, path: print(f"Saved to: {path}"))
viewer.error_occurred.connect(lambda msg: print(f"Error: {msg}"))
```

### Using Presets

```python
from pdfjs_viewer import PDFViewerWidget

# Use a preset directly
viewer = PDFViewerWidget(preset="annotation")

# Customize a preset
viewer = PDFViewerWidget(
    preset="simple",
    customize={"features": {"ink_enabled": True}}
)
```

### Handling Unsaved Changes

```python
from pdfjs_viewer import PDFViewerWidget, ConfigPresets

# Enable unsaved changes protection
config = ConfigPresets.annotation()
config.features.unsaved_changes_action = "prompt"
viewer = PDFViewerWidget(config=config)

# Check before closing
if viewer.has_unsaved_changes():
    viewer.handle_unsaved_changes()  # Shows dialog
```

### Loading with Options

```python
# Open at page 5 with page-width zoom
viewer.load_pdf("document.pdf", page=5, zoom="page-width")

# Open with bookmarks sidebar
viewer.load_pdf("document.pdf", pagemode="bookmarks")
```

## Need More Help?

- Check the main [README.md](../README.md) for full documentation
- Report issues on GitHub
