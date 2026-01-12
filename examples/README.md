# PDF.js Viewer Examples

This directory contains examples demonstrating various features and use cases of the `pdfjs-viewer-pyside6` package.

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

## Document Viewer Patterns

### [generic_document_viewer.py](generic_document_viewer.py)
**Full document viewer application pattern**
- Menu bar, toolbar, status bar
- File operations (open, save, recent files)
- Page navigation controls
- Zoom controls
- Example of a complete document viewing application

## Stability & Crash Prevention

### [stability_demo.py](stability_demo.py)
**Stability configuration examples**
- Shows PDFStabilityConfig options
- Demonstrates crash prevention settings
- Useful for embedded environments or older systems

### [ultra_stability_example.py](ultra_stability_example.py)
**Maximum stability configuration**
- All stability features enabled
- Optimized for reliability over features
- Use when crashes are a concern

## Testing (Not Production Examples)

### [test_alttext_dialog_crash.py](test_alttext_dialog_crash.py)
**Test file for alt-text dialog crashes in Qt 6.10.1** - NOT A PRODUCTION EXAMPLE
- Used for testing alt-text dialog behavior
- Demonstrates crash scenarios and fixes
- For development/testing purposes only

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
- **Building a document viewer app?** → `generic_document_viewer.py`
- **Having stability issues?** → `stability_demo.py` or `ultra_stability_example.py`
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

## Need More Help?

- Check the main [README.md](../README.md) for full documentation
- Report issues on GitHub
