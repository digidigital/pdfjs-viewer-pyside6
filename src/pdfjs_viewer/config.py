"""Configuration classes for PDF.js Viewer Widget."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List

class PrintHandler(str, Enum):
    """Print handler options.

    SYSTEM: Open PDF with system default viewer (simple, reliable)
    QT_DIALOG: Use Qt print dialog with pypdfium2 rendering (requires pypdfium2)
    EMIT_SIGNAL: Emit signal with PDF data for custom handling
    """
    SYSTEM = "system"
    QT_DIALOG = "qt_dialog"
    EMIT_SIGNAL = "emit_signal"


@dataclass
class PDFFeatures:
    """Feature flags for UI elements.

    Controls which features are enabled/visible in the PDF viewer interface.
    """
    # Core actions
    print_enabled: bool = True
    save_enabled: bool = True
    load_enabled: bool = True
    presentation_mode: bool = False

    # Annotation tools
    highlight_enabled: bool = True
    freetext_enabled: bool = True
    ink_enabled: bool = True
    stamp_enabled: bool = True
    stamp_alttext_enabled: bool = True  # Enable/disable alt-text dialog for stamps
    # Note: Signature and Comment tools not exposed in PDF.js UI yet
    # Uncomment when PDF.js UI provides these tools
    # signature_enabled: bool = True
    # comment_enabled: bool = True

    # Navigation and view modes
    bookmark_enabled: bool = False
    scroll_mode_buttons: bool = True
    spread_mode_buttons: bool = True

    # Unsaved changes behavior: "disabled", "prompt", "auto_save"
    # - disabled: No warning, allow navigation without prompting
    # - prompt: Show dialog with Save As / Save / Discard options
    # - auto_save: Automatically save annotations before leaving
    unsaved_changes_action: str = "disabled"

    def __post_init__(self):
        """Validate configuration values."""
        valid_actions = ("disabled", "prompt", "auto_save")
        if self.unsaved_changes_action not in valid_actions:
            raise ValueError(
                f"unsaved_changes_action must be one of {valid_actions}, "
                f"got '{self.unsaved_changes_action}'"
            )

    def to_js_config(self) -> dict:
        """Convert to JavaScript configuration object."""
        return {
            "print": self.print_enabled,
            "save": self.save_enabled,
            "load": self.load_enabled,
            "presentation": self.presentation_mode,
            "highlight": self.highlight_enabled,
            "freetext": self.freetext_enabled,
            "ink": self.ink_enabled,
            "stamp": self.stamp_enabled,
            "stampAltText": self.stamp_alttext_enabled,
            # Signature and Comment not exposed in PDF.js UI yet
            # "signature": self.signature_enabled,
            # "comment": self.comment_enabled,
            "bookmark": self.bookmark_enabled,
            "scrollMode": self.scroll_mode_buttons,
            "spreadMode": self.spread_mode_buttons,
            "unsavedChangesAction": self.unsaved_changes_action,
        }


@dataclass
class PDFSecurityConfig:
    """Security settings for the PDF viewer.

    Controls external link access, remote content loading, and link confirmation.
    Note: JavaScript is always enabled (required for PDF.js viewer).
    Chromium sandbox is controlled globally via stability.configure_global_stability().
    """
    allow_external_links: bool = False
    confirm_before_external_link: bool = True  # Show confirmation dialog before opening
    block_remote_content: bool = True

    # Allowed protocols for links
    allowed_protocols: List[str] = field(
        default_factory=lambda: ["http", "https"]
    )

    # Content Security Policy (optional custom CSP)
    custom_csp: str = None


@dataclass
class PDFViewerConfig:
    """Main configuration for PDF viewer widget.

    Combines all configuration options including features, security, and behavior.
    """
    features: PDFFeatures = field(default_factory=PDFFeatures)
    security: PDFSecurityConfig = field(default_factory=PDFSecurityConfig)

    # Behavior
    auto_open_folder_on_save: bool = True
    disable_context_menu: bool = True  # Disable QWebEngine's native context menu

    # Print handling
    print_handler: PrintHandler = PrintHandler.SYSTEM
    print_dpi: int = 300  # DPI for Qt print dialog rendering
    print_fit_to_page: bool = True  # Scale to fit page vs actual size
    # Deprecated: print_parallel_pages is ignored (printing is now sequential)
    print_parallel_pages: int = 1  # Deprecated, kept for backwards compatibility

    # PDF.js settings
    default_zoom: str = "auto"  # "auto", "page-fit", "page-width", or percentage
    sidebar_visible: bool = False
    spread_mode: str = "none"  # "none", "odd", "even"

    def __post_init__(self):
        """Validate configuration and show deprecation warnings."""
        # Deprecation warning for print_parallel_pages
        if self.print_parallel_pages != 1:
            print(
                "DeprecationWarning: print_parallel_pages is deprecated and ignored. "
                "Printing is now sequential for better stability and memory management."
            )
            # Reset to 1 (ignored anyway, but for consistency)
            object.__setattr__(self, 'print_parallel_pages', 1)


def validate_pdf_file(file_path: str) -> bool:
    """Validate that a file is actually a PDF by checking magic bytes.

    Args:
        file_path: Path to file to validate

    Returns:
        True if file has PDF magic bytes, False otherwise

    Example:
        >>> from pdfjs_viewer.config import validate_pdf_file
        >>> validate_pdf_file("/path/to/document.pdf")
        True
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(4)
            return header == b'%PDF'
    except Exception:
        return False


class ConfigPresets:
    """Pre-configured settings for common PDF viewer use cases.

    Provides convenient presets that cover most use cases while allowing
    full customization through the standard PDFViewerConfig.

    Available Presets:
        - readonly: View-only with maximum security
        - simple: Basic viewing with print/save
        - annotation: Full editing and annotation tools
        - form: PDF form filling (with JavaScript support)
        - kiosk: Public terminal/display mode
        - safer: Maximum stability for embedded systems
        - unrestricted: Full PDF.js, no restrictions (default)

    Examples:
        Simple preset usage:
        >>> viewer = PDFViewerWidget(preset="readonly")

        Customized preset:
        >>> viewer = PDFViewerWidget(
        ...     preset="readonly",
        ...     customize={"features": {"save_enabled": True}}
        ... )

        Full control:
        >>> config = ConfigPresets.readonly()
        >>> config.features.save_enabled = True
        >>> viewer = PDFViewerWidget(config=config)

        List available presets:
        >>> ConfigPresets.list()
        ['readonly', 'simple', 'annotation', 'form', 'kiosk', 'safer', 'unrestricted']
    """

    @staticmethod
    def list() -> List[str]:
        """List all available preset names.

        Returns:
            List of preset names
        """
        return [
            "readonly",
            "simple",
            "annotation",
            "form",
            "kiosk",
            "safer",
            "unrestricted"
        ]

    @staticmethod
    def readonly() -> PDFViewerConfig:
        """View-only mode with maximum security.

        Use Cases:
            - Document viewer in kiosk mode
            - Embedded PDF display
            - Untrusted PDF viewing

        Features:
            - No editing, no saving, no printing
            - No external links
            - No remote content
            - Maximum security
        """
        return PDFViewerConfig(
            features=PDFFeatures(
                print_enabled=False,
                save_enabled=False,
                load_enabled=False,
                presentation_mode=False,
                highlight_enabled=False,
                freetext_enabled=False,
                ink_enabled=False,
                stamp_enabled=False,
                stamp_alttext_enabled=False,
                # signature_enabled=False,  # Not exposed in UI yet
                # comment_enabled=False,  # Not exposed in UI yet
                bookmark_enabled=False,
                scroll_mode_buttons=False,
                spread_mode_buttons=False,
                unsaved_changes_action="disabled",  # No editing possible
            ),
            security=PDFSecurityConfig(
                allow_external_links=False,
                confirm_before_external_link=True,
                block_remote_content=True,
                allowed_protocols=[],
            ),
            auto_open_folder_on_save=False,
            disable_context_menu=True,
            print_handler=PrintHandler.SYSTEM,
            sidebar_visible=True,
        )

    @staticmethod
    def simple() -> PDFViewerConfig:
        """Basic viewer for general use.

        Use Cases:
            - Standard PDF viewing
            - Most common use case
            - Balance of features and simplicity

        Features:
            - Print and save enabled
            - Light annotation (highlight, text)
            - External links allowed
            - No advanced annotation tools
        """
        return PDFViewerConfig(
            features=PDFFeatures(
                print_enabled=True,
                save_enabled=True,
                load_enabled=False,
                presentation_mode=False,
                highlight_enabled=True,
                freetext_enabled=True,
                ink_enabled=False,
                stamp_enabled=False,
                stamp_alttext_enabled=False,
                # signature_enabled=False,  # Not exposed in UI yet
                # comment_enabled=False,  # Not exposed in UI yet
                bookmark_enabled=False,
                scroll_mode_buttons=False,
                spread_mode_buttons=False,
                unsaved_changes_action="prompt",  # User decides
            ),
            security=PDFSecurityConfig(
                allow_external_links=True,
                confirm_before_external_link=True,
                block_remote_content=True,
                allowed_protocols=["http", "https"],
            ),
            auto_open_folder_on_save=True,
            disable_context_menu=True,
            print_handler=PrintHandler.SYSTEM,
            sidebar_visible=False,
        )

    @staticmethod
    def annotation() -> PDFViewerConfig:
        """Full annotation and editing tools.

        Use Cases:
            - PDF editing and review
            - Collaborative document annotation
            - Document workflows

        Features:
            - All annotation tools enabled
            - File loading enabled
            - External links and remote content allowed
            - Full productivity features
        """
        return PDFViewerConfig(
            features=PDFFeatures(
                print_enabled=True,
                save_enabled=True,
                load_enabled=True,
                presentation_mode=False,
                highlight_enabled=True,
                freetext_enabled=True,
                ink_enabled=True,
                stamp_enabled=True,
                stamp_alttext_enabled=True,
                # signature_enabled=True,  # Not exposed in UI yet
                # comment_enabled=True,  # Not exposed in UI yet
                bookmark_enabled=False,
                scroll_mode_buttons=True,
                spread_mode_buttons=True,
                unsaved_changes_action="prompt",  # User decides
            ),
            security=PDFSecurityConfig(
                allow_external_links=True,
                confirm_before_external_link=True,
                block_remote_content=False,
                allowed_protocols=["http", "https", "mailto"],
            ),
            auto_open_folder_on_save=True,
            disable_context_menu=True,  # We provide our own context menu
            print_handler=PrintHandler.QT_DIALOG,
            sidebar_visible=True,
        )

    @staticmethod
    def form() -> PDFViewerConfig:
        """PDF form filling focus.

        Use Cases:
            - Government forms
            - Insurance applications
            - Contract signing

        Features:
            - Text input and signatures
            - Form-specific tools
            - No external links (forms are self-contained)
        """
        return PDFViewerConfig(
            features=PDFFeatures(
                print_enabled=True,
                save_enabled=True,
                load_enabled=True,
                presentation_mode=False,
                highlight_enabled=False,
                freetext_enabled=True,
                ink_enabled=False,
                stamp_enabled=False,
                stamp_alttext_enabled=False,
                # signature_enabled=True,  # Not exposed in UI yet
                # comment_enabled=False,  # Not exposed in UI yet
                bookmark_enabled=False,
                scroll_mode_buttons=False,
                spread_mode_buttons=False,
                unsaved_changes_action="prompt",  # Forms often have unsaved data
            ),
            security=PDFSecurityConfig(
                allow_external_links=False,
                confirm_before_external_link=True,
                block_remote_content=True,
                allowed_protocols=[],
            ),
            auto_open_folder_on_save=True,
            disable_context_menu=True,
            print_handler=PrintHandler.QT_DIALOG,
            sidebar_visible=False,
        )

    @staticmethod
    def kiosk() -> PDFViewerConfig:
        """Public display terminal mode.

        Use Cases:
            - Library catalog viewers
            - Museum information kiosks
            - Public information terminals

        Features:
            - Print allowed (for public info)
            - No saving or editing
            - No external links
            - Maximum stability for 24/7 operation
        """
        return PDFViewerConfig(
            features=PDFFeatures(
                print_enabled=True,
                save_enabled=False,
                load_enabled=False,
                presentation_mode=False,
                highlight_enabled=False,
                freetext_enabled=False,
                ink_enabled=False,
                stamp_enabled=False,
                stamp_alttext_enabled=False,
                # signature_enabled=False,  # Not exposed in UI yet
                # comment_enabled=False,  # Not exposed in UI yet
                bookmark_enabled=False,
                scroll_mode_buttons=True,
                spread_mode_buttons=False,
                unsaved_changes_action="disabled",  # No user interaction for prompts
            ),
            security=PDFSecurityConfig(
                allow_external_links=False,
                confirm_before_external_link=True,
                block_remote_content=True,
                allowed_protocols=[],
            ),
            auto_open_folder_on_save=False,
            disable_context_menu=True,
            print_handler=PrintHandler.SYSTEM,
            sidebar_visible=False,
        )

    @staticmethod
    def safer() -> PDFViewerConfig:
        """Maximum stability for crash-prone systems.

        Use Cases:
            - Embedded Linux devices
            - Older Qt versions
            - Systems with GPU issues
            - Mission-critical applications

        Features:
            - Minimal features for maximum stability
            - All stability features enabled
            - No annotation tools
            - Basic viewing only
        """
        return PDFViewerConfig(
            features=PDFFeatures(
                print_enabled=True,
                save_enabled=True,
                load_enabled=False,
                presentation_mode=False,
                highlight_enabled=False,
                freetext_enabled=False,
                ink_enabled=False,
                stamp_enabled=False,
                stamp_alttext_enabled=False,
                # signature_enabled=False,  # Not exposed in UI yet
                # comment_enabled=False,  # Not exposed in UI yet
                bookmark_enabled=False,
                scroll_mode_buttons=False,
                spread_mode_buttons=False,
                unsaved_changes_action="prompt",  # Prevent data loss
            ),
            security=PDFSecurityConfig(
                allow_external_links=False,
                confirm_before_external_link=True,
                block_remote_content=True,
                allowed_protocols=[],
            ),
            auto_open_folder_on_save=True,
            disable_context_menu=True,
            print_handler=PrintHandler.SYSTEM,
            sidebar_visible=False,
        )

    @staticmethod
    def unrestricted() -> PDFViewerConfig:
        """Full PDF.js with no restrictions (default).

        Use Cases:
            - Development and testing
            - Fully trusted PDFs
            - Maximum feature set

        Features:
            - All PDF.js features available
            - Minimal restrictions
            - Developer-friendly defaults
        """
        return PDFViewerConfig(
            features=PDFFeatures(
                # Core actions - all enabled
                print_enabled=True,
                save_enabled=True,
                load_enabled=True,
                presentation_mode=True,

                # Annotation tools - all enabled
                highlight_enabled=True,
                freetext_enabled=True,
                ink_enabled=True,
                stamp_enabled=True,
                stamp_alttext_enabled=True,

                # Navigation and view modes - all enabled
                bookmark_enabled=True,
                scroll_mode_buttons=True,
                spread_mode_buttons=True,
                unsaved_changes_action="disabled",  # Backwards compatible
            )
        )

    @staticmethod
    def get(preset_name: str) -> PDFViewerConfig:
        """Get a preset configuration by name.

        Args:
            preset_name: Name of the preset

        Returns:
            PDFViewerConfig for the preset

        Raises:
            ValueError: If preset name is unknown

        Example:
            >>> config = ConfigPresets.get("readonly")
        """
        preset_map = {
            "readonly": ConfigPresets.readonly,
            "simple": ConfigPresets.simple,
            "annotation": ConfigPresets.annotation,
            "form": ConfigPresets.form,
            "kiosk": ConfigPresets.kiosk,
            "safer": ConfigPresets.safer,
            "unrestricted": ConfigPresets.unrestricted,
        }

        if preset_name not in preset_map:
            available = ", ".join(ConfigPresets.list())
            raise ValueError(
                f"Unknown preset '{preset_name}'. "
                f"Available presets: {available}"
            )

        return preset_map[preset_name]()

    @staticmethod
    def custom(base: str = "unrestricted", **overrides) -> PDFViewerConfig:
        """Create a custom configuration starting from a preset.

        Args:
            base: Preset name to start from (default: "unrestricted")
            **overrides: Nested dict of setting overrides

        Returns:
            Customized PDFViewerConfig

        Example:
            >>> config = ConfigPresets.custom(
            ...     base="readonly",
            ...     features={"save_enabled": True},
            ...     security={"allow_external_links": True}
            ... )

        Raises:
            ValueError: If base preset is unknown
        """
        config = ConfigPresets.get(base)

        # Apply overrides
        for category, settings in overrides.items():
            if not isinstance(settings, dict):
                raise ValueError(
                    f"Override for '{category}' must be a dict, "
                    f"got {type(settings).__name__}"
                )

            # Get the config category object
            if category == "features":
                obj = config.features
            elif category == "security":
                obj = config.security
            elif category in dir(config):
                # Direct config attribute
                for key, value in settings.items():
                    setattr(config, key, value)
                continue
            else:
                raise ValueError(
                    f"Unknown config category '{category}'. "
                    f"Valid: features, security, or config attributes"
                )

            # Apply settings to category
            for key, value in settings.items():
                if not hasattr(obj, key):
                    raise ValueError(
                        f"Unknown setting '{key}' in category '{category}'"
                    )
                setattr(obj, key, value)

        return config
