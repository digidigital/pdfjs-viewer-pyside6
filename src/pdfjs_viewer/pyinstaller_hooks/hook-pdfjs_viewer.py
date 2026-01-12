"""PyInstaller hook for pdfjs_viewer.

This hook ensures that all necessary files and hidden imports are included
when freezing applications that use pdfjs_viewer.

PyInstaller will automatically use this hook if the package is installed.
No manual configuration needed!
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from pathlib import Path

# Get the package directory
try:
    import pdfjs_viewer
    package_dir = Path(pdfjs_viewer.__file__).parent
except ImportError:
    package_dir = None

# Hidden imports - ensure print_process module is included
hiddenimports = [
    'pdfjs_viewer.print_process',
    'pdfjs_viewer.print_process.main',
    'pdfjs_viewer.print_manager',
]

# Data files to include
datas = []

if package_dir and package_dir.exists():
    # Include PDF.js library files (web viewer)
    pdfjs_dir = package_dir / 'pdfjs'
    if pdfjs_dir.exists():
        datas.append((str(pdfjs_dir), 'pdfjs_viewer/pdfjs'))

    # Include print_process module (CRITICAL for separate process printing)
    print_process_dir = package_dir / 'print_process'
    if print_process_dir.exists():
        datas.append((str(print_process_dir), 'pdfjs_viewer/print_process'))

    # Include translations if present
    translations_dir = package_dir / 'translations'
    if translations_dir.exists():
        datas.append((str(translations_dir), 'pdfjs_viewer/translations'))

# Also collect any additional data files
datas += collect_data_files('pdfjs_viewer', include_py_files=True)
