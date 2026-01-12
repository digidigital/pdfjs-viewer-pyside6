"""Entry point for print_process when run as module."""

import sys
from .main import main

if __name__ == '__main__':
    # Required for Windows multiprocessing/QProcess to avoid infinite spawning
    if sys.platform == 'win32':
        try:
            import multiprocessing
            multiprocessing.freeze_support()
        except ImportError:
            pass  # multiprocessing not available, QProcess will handle it

    main()
