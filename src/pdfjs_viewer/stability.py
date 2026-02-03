"""Global stability configuration and environment variable handling.

This module provides functions to configure WebEngine stability settings
at the application level before QApplication is created.
"""

import os
import sys
from typing import List, Optional


def configure_global_stability(
    disable_gpu: bool = True,
    disable_sandbox: bool = False,
    disable_software_rasterizer: bool = False,
    disable_webgl: bool = True,
    disable_gpu_compositing: bool = True,
    single_process: bool = False,
    disable_unnecessary_features: bool = True,
    extra_args: Optional[List[str]] = None
):
    """Configure global WebEngine stability settings.

    IMPORTANT: Must be called BEFORE creating QApplication instance.

    These settings apply globally to all QWebEngine instances in the application.

    Args:
        disable_gpu: Disable GPU acceleration (recommended for stability)
        disable_sandbox: Disable Chromium sandbox (use cautiously)
        disable_software_rasterizer: Disable software rasterizer fallback
        disable_webgl: Disable WebGL (major crash source)
        disable_gpu_compositing: Disable GPU compositing
        single_process: Run WebEngine in single process mode (less isolation)
        disable_unnecessary_features: Disable features not needed for PDF viewing
                                      (audio, WebRTC, notifications, etc.)
        extra_args: Additional Chromium command line arguments

    Example:
        >>> from pdfjs_viewer.stability import configure_global_stability
        >>> configure_global_stability(disable_gpu=True, disable_webgl=True)
        >>> app = QApplication(sys.argv)  # Create app AFTER configuration
    """
    args = []

    # GPU and rendering stability
    if disable_gpu:
        args.extend([
            "--disable-gpu",
            "--disable-gpu-vsync",
            "--disable-gpu-watchdog",
        ])
        if disable_software_rasterizer:
            args.append("--disable-software-rasterizer")

    if disable_webgl:
        args.extend([
            "--disable-webgl",
            "--disable-webgl2",
        ])

    if disable_gpu_compositing:
        args.append("--disable-gpu-compositing")

    if disable_sandbox:
        args.append("--no-sandbox")

    if single_process:
        args.append("--single-process")

    # Disable features unnecessary for PDF viewing
    if disable_unnecessary_features:
        args.extend([
            # Performance/Logging
            "--log-level=0",

            # Network (PDFs are local files)
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-domain-reliability",
            "--disable-sync",
            "--no-pings",

            # Media (PDFs don't need audio/video)
            "--disable-audio-output",
            "--disable-audio-support",
            "--disable-speech-api",
            "--autoplay-policy=document-user-activation-required",

            # WebRTC (major crash source, not needed for PDFs)
            "--disable-webrtc",

            # UI features (not needed)
            "--disable-notifications",
            "--disable-print-preview",
            "--no-first-run",
            "--no-default-browser-check",

            # Background processing
            "--disable-backgrounding-occluded-windows",
            "--disable-hang-monitor",

            # Smooth scrolling (simpler rendering)
            "--disable-smooth-scrolling",
        ])

    # Add extra args
    if extra_args:
        args.extend(extra_args)

    # Filter empty strings
    args = [arg for arg in args if arg]

    # Set environment variable for QtWebEngine
    if args:
        existing_args = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        if existing_args:
            args = existing_args.split() + args

        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(args)


def apply_environment_stability():
    """Apply stability settings from environment variables.

    Reads standard QtWebEngine environment variables and applies them.
    Call this BEFORE creating QApplication.

    Supported environment variables:
        QTWEBENGINE_CHROMIUM_FLAGS: Additional Chromium flags
        QTWEBENGINE_DISABLE_SANDBOX: Disable sandbox (1/true/yes)
        PDFJS_VIEWER_SAFER_MODE: Enable safer mode preset (1/true/yes)

    Example:
        >>> from pdfjs_viewer.stability import apply_environment_stability
        >>> apply_environment_stability()
        >>> app = QApplication(sys.argv)
    """
    # Check for safer mode environment variable
    safer_mode = os.environ.get("PDFJS_VIEWER_SAFER_MODE", "").lower() in ("1", "true", "yes")

    if safer_mode:
        configure_global_stability(
            disable_gpu=True,
            disable_webgl=True,
            disable_gpu_compositing=True,
            disable_unnecessary_features=True,
        )

    # Check for sandbox disable
    disable_sandbox = os.environ.get("QTWEBENGINE_DISABLE_SANDBOX", "").lower() in ("1", "true", "yes")

    if disable_sandbox:
        existing_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        if "--no-sandbox" not in existing_flags:
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{existing_flags} --no-sandbox".strip()


def print_stability_info():
    """Print current stability configuration to stdout.

    Useful for debugging and verifying configuration.
    """
    print("=== WebEngine Stability Configuration ===")
    print(f"QTWEBENGINE_CHROMIUM_FLAGS: {os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '(not set)')}")
    print(f"QTWEBENGINE_DISABLE_SANDBOX: {os.environ.get('QTWEBENGINE_DISABLE_SANDBOX', '(not set)')}")
    print(f"PDFJS_VIEWER_SAFER_MODE: {os.environ.get('PDFJS_VIEWER_SAFER_MODE', '(not set)')}")
    print("=========================================")
