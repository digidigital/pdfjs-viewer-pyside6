"""PyInstaller hook for pdfjs_viewer.

This hook ensures that all necessary files and hidden imports are included
when freezing applications that use pdfjs_viewer.

Auto-discovered via the pyinstaller40 entry point in pyproject.toml
"""

from PyInstaller.utils.hooks import collect_all


datas, binaries, hiddenimports = collect_all('pdfjs_viewer', include_py_files=True)