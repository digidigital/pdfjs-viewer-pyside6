from typing import List
import os


def get_hook_dirs() -> List[str]:
    return [os.path.join(os.path.dirname(__file__), 'pdfjs_viewer', 'pyinstaller_hooks')]
