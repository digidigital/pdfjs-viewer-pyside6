# PDF.js Viewer Stability Guide

This guide explains how to configure the PDF.js viewer for maximum stability and crash prevention.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Stability Levels](#stability-levels)
- [Configuration Options](#configuration-options)
- [Global vs Per-Viewer Settings](#global-vs-per-viewer-settings)
- [Common Crash Scenarios](#common-crash-scenarios)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

QWebEngine (Chromium-based) can crash due to various factors:
- GPU/WebGL operations
- Memory issues with caching/storage
- Service worker conflicts
- Background networking issues

This viewer provides comprehensive stability controls to prevent crashes.

## Quick Start

### Recommended: Safer Mode (Default)

The simplest approach - safer mode is **enabled by default**:

```python
from pdfjs_viewer import PDFViewerWidget

# Uses safer mode by default (stability.safer_mode=True)
viewer = PDFViewerWidget()
```

Safer mode automatically applies:
- ✓ Isolated profile per viewer
- ✓ WebGL disabled
- ✓ GPU acceleration disabled
- ✓ Cache disabled
- ✓ Local storage disabled
- ✓ Service workers disabled

### Maximum Stability

For production or crash-prone environments:

```python
from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig
from pdfjs_viewer.stability import get_maximum_stability_config
from pdfjs_viewer.config import PDFStabilityConfig

config = PDFViewerConfig(
    stability=PDFStabilityConfig(**get_maximum_stability_config())
)

viewer = PDFViewerWidget(config=config)
```

### Global Stability Settings

For application-wide configuration (before QApplication):

```python
from pdfjs_viewer.stability import configure_global_stability
from PyQt6.QtWidgets import QApplication
import sys

# MUST be called BEFORE QApplication
configure_global_stability(
    disable_gpu=True,
    disable_webgl=True,
    disable_gpu_compositing=True
)

app = QApplication(sys.argv)
# ... rest of your application
```

## Stability Levels

### Level 1: Default (Safer Mode)

**Crash Reduction: ~60-70%**

Enabled by default. Balances stability and functionality.

```python
from pdfjs_viewer import PDFViewerWidget

viewer = PDFViewerWidget()  # safer_mode=True by default
```

### Level 2: Recommended Production

**Crash Reduction: ~75-85%**

Recommended for production applications.

```python
from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig
from pdfjs_viewer.stability import get_recommended_stability_config
from pdfjs_viewer.config import PDFStabilityConfig

config = PDFViewerConfig(
    stability=PDFStabilityConfig(**get_recommended_stability_config())
)

viewer = PDFViewerWidget(config=config)
```

### Level 3: Maximum Stability

**Crash Reduction: ~85-95%**

Most restrictive. Use when crashes are frequent.

```python
from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig
from pdfjs_viewer.stability import get_maximum_stability_config
from pdfjs_viewer.config import PDFStabilityConfig

config = PDFViewerConfig(
    stability=PDFStabilityConfig(**get_maximum_stability_config())
)

viewer = PDFViewerWidget(config=config)
```

### Level 4: Custom Configuration

Fine-tune individual settings:

```python
from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig
from pdfjs_viewer.config import PDFStabilityConfig

config = PDFViewerConfig(
    stability=PDFStabilityConfig(
        use_isolated_profile=True,
        disable_webgl=True,
        disable_gpu=True,
        disable_cache=False,  # Enable cache for performance
        safer_mode=False  # Use custom settings
    )
)

viewer = PDFViewerWidget(config=config)
```

## Configuration Options

### PDFStabilityConfig

```python
from pdfjs_viewer.config import PDFStabilityConfig

stability = PDFStabilityConfig(
    # Profile isolation (highly recommended)
    use_isolated_profile=True,  # Each viewer gets own profile
    profile_name=None,  # Auto-generated if None

    # GPU and WebGL (major crash sources)
    disable_webgl=True,  # Disable WebGL rendering
    disable_gpu=True,  # Disable GPU acceleration
    disable_gpu_compositing=True,  # Disable GPU compositing

    # Cache and storage
    disable_cache=True,  # Disable disk cache
    disable_local_storage=True,  # Disable localStorage
    disable_session_storage=True,  # Disable sessionStorage
    disable_databases=True,  # Disable Web SQL/IndexedDB

    # Service workers and background
    disable_service_workers=True,  # Disable service workers
    disable_background_networking=True,  # Disable background requests

    # Rendering
    disable_software_rasterizer=False,  # Keep software rendering
    force_prefers_reduced_motion=False,  # Reduce animations

    # Memory
    max_cache_size_mb=0,  # 0 = minimal cache

    # Preset
    safer_mode=True  # Override with safe defaults
)
```

## Global vs Per-Viewer Settings

### Global Settings (Application-Wide)

Apply to **all** QWebEngine instances. Must be set **before** QApplication:

```python
from pdfjs_viewer.stability import configure_global_stability

# BEFORE QApplication
configure_global_stability(
    disable_gpu=True,
    disable_webgl=True
)

from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
```

**Environment Variables:**

```bash
# Enable safer mode globally
export PDFJS_VIEWER_SAFER_MODE=1

# Disable sandbox (use cautiously)
export QTWEBENGINE_DISABLE_SANDBOX=1

# Custom Chromium flags
export QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --disable-webgl"

python your_app.py
```

### Per-Viewer Settings

Apply to individual viewers:

```python
from pdfjs_viewer import PDFViewerWidget, PDFViewerConfig
from pdfjs_viewer.config import PDFStabilityConfig

# Viewer 1: Maximum stability
config1 = PDFViewerConfig(
    stability=PDFStabilityConfig(safer_mode=True)
)
viewer1 = PDFViewerWidget(config=config1)

# Viewer 2: Performance mode
config2 = PDFViewerConfig(
    stability=PDFStabilityConfig(
        safer_mode=False,
        disable_cache=False  # Enable cache
    )
)
viewer2 = PDFViewerWidget(config=config2)
```

## Common Crash Scenarios

### Scenario 1: Random WebGL Crashes

**Symptoms:** Crashes when viewing certain PDFs, especially with complex graphics.

**Solution:**
```python
config = PDFViewerConfig(
    stability=PDFStabilityConfig(
        disable_webgl=True,
        disable_gpu=True
    )
)
```

### Scenario 2: Memory/Cache Related Crashes

**Symptoms:** Crashes after viewing many PDFs or after extended use.

**Solution:**
```python
config = PDFViewerConfig(
    stability=PDFStabilityConfig(
        disable_cache=True,
        disable_local_storage=True,
        max_cache_size_mb=0
    )
)
```

### Scenario 3: Multi-Viewer Crashes

**Symptoms:** Crashes when using multiple viewers simultaneously.

**Solution:**
```python
config = PDFViewerConfig(
    stability=PDFStabilityConfig(
        use_isolated_profile=True  # Each viewer gets own profile
    )
)

viewer1 = PDFViewerWidget(config=config)
viewer2 = PDFViewerWidget(config=config)  # Separate profile
```

### Scenario 4: Shutdown Crashes (Speicherzugriffsfehler)

**Symptoms:** Crashes when closing application or viewer.

**Solution:**
```python
# Always call cleanup
viewer.close()  # Triggers cleanup automatically

# Or manually:
viewer.backend.cleanup()
```

## Best Practices

### 1. Use Safer Mode by Default

```python
# Good - safer mode enabled by default
viewer = PDFViewerWidget()

# Avoid - disabling safer mode without reason
config = PDFViewerConfig(
    stability=PDFStabilityConfig(safer_mode=False)
)
viewer = PDFViewerWidget(config=config)
```

### 2. Use Profile Isolation for Multiple Viewers

```python
# Good - each viewer isolated
config = PDFViewerConfig(
    stability=PDFStabilityConfig(use_isolated_profile=True)
)

viewer1 = PDFViewerWidget(config=config)
viewer2 = PDFViewerWidget(config=config)

# Avoid - sharing default profile
config = PDFViewerConfig(
    stability=PDFStabilityConfig(use_isolated_profile=False)
)
```

### 3. Always Cleanup on Close

```python
class MainWindow(QMainWindow):
    def closeEvent(self, event):
        # Cleanup viewer before closing
        self.viewer.backend.cleanup()
        super().closeEvent(event)
```

### 4. Use Global Settings for Application-Wide Stability

```python
# main.py
from pdfjs_viewer.stability import apply_environment_stability

# Apply BEFORE QApplication
apply_environment_stability()

from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
# ...
```

### 5. Test with Different Stability Levels

Start with maximum stability, then relax if needed:

```python
# Phase 1: Test with maximum stability
config = get_maximum_stability_config()

# Phase 2: If stable, relax some settings for performance
config['disable_cache'] = False  # Enable cache
config['max_cache_size_mb'] = 50  # 50MB cache

# Phase 3: Monitor and adjust
```

## Troubleshooting

### Issue: Viewer Still Crashes

**Check:**
1. Are you using safer mode? `stability.safer_mode=True`
2. Is profile isolation enabled? `use_isolated_profile=True`
3. Are GPU/WebGL disabled? `disable_gpu=True`, `disable_webgl=True`
4. Did you call `cleanup()` on close?

**Try:**
```python
from pdfjs_viewer.stability import get_maximum_stability_config

config = PDFViewerConfig(
    stability=PDFStabilityConfig(**get_maximum_stability_config())
)
```

### Issue: Performance is Too Slow

**Solution:** Relax some settings while keeping critical ones:

```python
config = PDFViewerConfig(
    stability=PDFStabilityConfig(
        # Keep critical stability settings
        use_isolated_profile=True,
        disable_webgl=True,
        disable_gpu=True,

        # Relax for performance
        disable_cache=False,  # Enable cache
        max_cache_size_mb=100,  # 100MB cache
        disable_local_storage=False,  # Enable storage

        safer_mode=False  # Use custom config
    )
)
```

### Issue: Multiple Viewers Conflict

**Solution:** Ensure profile isolation:

```python
config = PDFViewerConfig(
    stability=PDFStabilityConfig(
        use_isolated_profile=True,
        profile_name=None  # Auto-generate unique names
    )
)

# Each viewer gets isolated profile
viewer1 = PDFViewerWidget(config=config)
viewer2 = PDFViewerWidget(config=config)
viewer3 = PDFViewerWidget(config=config)
```

### Debug: Print Current Configuration

```python
from pdfjs_viewer.stability import print_stability_info

print_stability_info()
# Shows environment variables and global settings
```

## Summary

**Quick Recommendations:**

| Use Case | Configuration |
|----------|--------------|
| Development | Default (safer_mode=True) |
| Production | `get_recommended_stability_config()` |
| High Crash Rate | `get_maximum_stability_config()` |
| Multiple Viewers | `use_isolated_profile=True` |
| Performance Critical | Custom config, enable cache |

**Most Important Settings:**

1. `safer_mode=True` (enabled by default)
2. `use_isolated_profile=True` (for multiple viewers)
3. `disable_webgl=True` (major crash source)
4. `disable_gpu=True` (major crash source)
5. Always call `cleanup()` on close

**Next Steps:**

- See [examples/](../examples/) for working examples
