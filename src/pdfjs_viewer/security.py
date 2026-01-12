"""Security manager for QWebEngineView and PDF viewer."""

from typing import Optional

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
)
from PySide6.QtGui import QDesktopServices

from .config import PDFSecurityConfig


class PDFWebEnginePage(QWebEnginePage):
    """Custom QWebEnginePage with security controls and link handling."""

    def __init__(
        self,
        profile: QWebEngineProfile,
        security_config: PDFSecurityConfig,
        parent=None
    ):
        """Initialize secure web engine page.

        Args:
            profile: QWebEngineProfile with security settings.
            security_config: Security configuration.
            parent: Parent widget.
        """
        super().__init__(profile, parent)
        self.security_config = security_config
        self._parent_widget = parent

    def acceptNavigationRequest(
        self,
        url: QUrl,
        nav_type: QWebEnginePage.NavigationType,
        is_main_frame: bool
    ) -> bool:
        """Control navigation requests based on security policy.

        Args:
            url: Target URL.
            nav_type: Type of navigation.
            is_main_frame: Whether this is the main frame.

        Returns:
            True if navigation is allowed, False otherwise.
        """
        scheme = url.scheme().lower()

        # Always allow file:// URLs for local PDFs
        if scheme == "file":
            return True

        # Allow data: URLs (used by PDF.js)
        if scheme == "data":
            return True

        # Allow blob: URLs (used by PDF.js for rendering)
        if scheme == "blob":
            return True

        # Handle http/https links
        if scheme in ["http", "https"]:
            if not self.security_config.allow_external_links:
                # Block and emit signal
                if self._parent_widget and hasattr(
                    self._parent_widget, 'external_link_blocked'
                ):
                    self._parent_widget.external_link_blocked.emit(url.toString())
                return False

            # Open in external browser instead of navigating
            if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
                QDesktopServices.openUrl(url)
                return False

            # Allow loading remote content if configured
            return not self.security_config.block_remote_content

        # Block all other schemes
        return False

    def javaScriptConsoleMessage(
        self,
        level: QWebEnginePage.JavaScriptConsoleMessageLevel,
        message: str,
        line_number: int,
        source_id: str
    ):
        """Log JavaScript console messages for debugging.

        Args:
            level: Message level (Info, Warning, Error).
            message: Console message.
            line_number: Line number in source.
            source_id: Source file ID.
        """
        level_str = {
            QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel: "INFO",
            QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel: "WARNING",
            QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel: "ERROR",
        }.get(level, "LOG")

        # Optionally log to console (can be disabled in production)
        # print(f"[JS {level_str}] {source_id}:{line_number} - {message}")


class PDFSecurityManager:
    """Manages security settings for QWebEngineView.

    Configures QWebEngineProfile, settings, and creates secure pages.
    """

    def __init__(self, security_config: Optional[PDFSecurityConfig] = None):
        """Initialize security manager.

        Args:
            security_config: Security configuration. If None, uses defaults.
        """
        self.config = security_config or PDFSecurityConfig()
        self.profile: Optional[QWebEngineProfile] = None

    def configure_profile(self) -> QWebEngineProfile:
        """Create and configure QWebEngineProfile with security settings.

        Returns:
            Configured QWebEngineProfile instance.
        """
        # Create isolated profile (not shared)
        profile = QWebEngineProfile()

        # Disable HTTP cache for security
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)

        # Disable persistent storage
        profile.setPersistentStoragePath("")

        # Configure settings
        settings = profile.settings()

        # JavaScript is required for PDF.js
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled,
            True
        )

        # Local content access
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            True  # Required for loading local PDFs
        )

        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            not self.config.block_remote_content
        )

        # Disable plugins
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.PluginsEnabled,
            False
        )

        # Allow images (needed for PDF rendering)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.AutoLoadImages,
            True
        )

        # Disable WebGL (not needed for PDF.js)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.WebGLEnabled,
            False
        )

        # Enable PDF.js to use web workers
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalStorageEnabled,
            False  # Disabled for security
        )

        # Disable fullscreen (presentation mode can be controlled separately)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.FullScreenSupportEnabled,
            True  # Allow for presentation mode
        )

        self.profile = profile
        return profile

    def create_page(self, profile=None, parent=None) -> PDFWebEnginePage:
        """Create a secure QWebEnginePage instance.

        Args:
            profile: Optional QWebEngineProfile to use (for profile isolation).
                    If None, uses the manager's configured profile.
            parent: Parent widget.

        Returns:
            Configured PDFWebEnginePage instance.
        """
        if profile is None:
            if self.profile is None:
                self.configure_profile()
            profile = self.profile

        return PDFWebEnginePage(profile, self.config, parent)

    def validate_url(self, url: QUrl) -> bool:
        """Validate URL against security policy.

        Args:
            url: URL to validate.

        Returns:
            True if URL is allowed, False otherwise.
        """
        scheme = url.scheme().lower()

        # Allow local files
        if scheme == "file":
            return True

        # Allow data and blob URLs
        if scheme in ["data", "blob"]:
            return True

        # Check remote content
        if scheme in ["http", "https"]:
            if self.config.block_remote_content:
                return False
            return True

        # Check custom protocols
        if scheme in self.config.allowed_protocols:
            return True

        return False
