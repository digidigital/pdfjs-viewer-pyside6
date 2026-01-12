"""Resource path management for PDF.js files."""

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QUrl


class PDFResourceManager:
    """Manages PDF.js resource paths and validation.

    Handles both bundled PDF.js files and custom PDF.js installations.
    Works correctly in both development and PyInstaller frozen environments.
    """

    def __init__(self, custom_pdfjs_path: Optional[str] = None):
        """Initialize resource manager.

        Args:
            custom_pdfjs_path: Path to custom PDF.js installation (optional).
                             If None, uses bundled PDF.js.
        """
        self.custom_path = Path(custom_pdfjs_path) if custom_pdfjs_path else None

    def get_pdfjs_path(self) -> Path:
        """Get path to PDF.js files (bundled or custom).

        Returns:
            Path to PDF.js directory containing web/ and build/ subdirectories.

        Raises:
            ValueError: If custom path is invalid or bundled files not found.
        """
        if self.custom_path:
            if self.validate_pdfjs_installation(self.custom_path):
                return self.custom_path
            else:
                raise ValueError(
                    f"Invalid PDF.js installation at {self.custom_path}. "
                    f"Required files missing."
                )

        # Return bundled PDF.js
        bundled_path = self._get_bundled_path() / "pdfjs"

        if not self.validate_pdfjs_installation(bundled_path):
            raise ValueError(
                f"Bundled PDF.js files not found at {bundled_path}. "
                f"Package may be corrupted."
            )

        return bundled_path

    def _get_bundled_path(self) -> Path:
        """Get path to bundled resources.

        Handles both development and PyInstaller frozen environments.
        For PyInstaller >= 5.0, resources are in _internal subdirectory.

        Returns:
            Path to package root directory.
        """
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller bundle
            if hasattr(sys, '_MEIPASS'):
                # Onefile mode: temporary extraction directory
                base_path = Path(sys._MEIPASS) / 'pdfjs_viewer'
            else:
                # Onedir mode (PyInstaller >= 5.0): resources in _internal
                exe_dir = Path(sys.executable).parent

                # Check if _internal directory exists (modern PyInstaller)
                internal_dir = exe_dir / '_internal' / 'pdfjs_viewer'
                if internal_dir.exists():
                    base_path = internal_dir
                else:
                    # Fallback: old structure or different PyInstaller version
                    base_path = exe_dir / 'pdfjs_viewer'
        else:
            # Running in development
            base_path = Path(__file__).parent

        return base_path

    def validate_pdfjs_installation(self, path: Path) -> bool:
        """Validate that path contains a valid PDF.js installation.

        Args:
            path: Path to check for PDF.js files.

        Returns:
            True if all required files exist, False otherwise.
        """
        required_files = [
            "web/viewer.html",
            "web/viewer.mjs",
            "web/viewer.css",
            "build/pdf.mjs",
            "build/pdf.worker.mjs",
        ]

        return all((path / f).exists() for f in required_files)

    def get_viewer_url(self) -> QUrl:
        """Get URL to viewer.html.

        Returns:
            QUrl pointing to the PDF.js viewer.html file.
        """
        pdfjs_path = self.get_pdfjs_path()
        viewer_html = pdfjs_path / "web" / "viewer.html"
        return QUrl.fromLocalFile(str(viewer_html.absolute()))

    def get_blank_viewer_url(self) -> QUrl:
        """Get URL to blank viewer (no PDF loaded).

        Returns:
            QUrl pointing to the PDF.js viewer.html without file parameter.
        """
        return self.get_viewer_url()

    def get_pdfjs_version(self) -> str:
        """Read PDF.js version from VERSION file.

        Returns:
            Version string, or "unknown" if VERSION file not found.
        """
        try:
            version_file = self.get_pdfjs_path() / "VERSION"
            if version_file.exists():
                return version_file.read_text().strip()
        except Exception:
            pass

        return "unknown"

    def get_template_path(self, template_name: str) -> Path:
        """Get path to JavaScript template file.

        Args:
            template_name: Name of template file (e.g., "bridge.js").

        Returns:
            Path to template file.

        Raises:
            FileNotFoundError: If template file doesn't exist.
        """
        template_path = self._get_bundled_path() / "templates" / template_name

        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_name}")

        return template_path

    def load_template(self, template_name: str) -> str:
        """Load JavaScript template content.

        Args:
            template_name: Name of template file (e.g., "bridge.js").

        Returns:
            Template content as string.

        Raises:
            FileNotFoundError: If template file doesn't exist.
        """
        template_path = self.get_template_path(template_name)
        return template_path.read_text(encoding='utf-8')
