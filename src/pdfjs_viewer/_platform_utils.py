"""Platform helpers shared by backend_inprocess and security modules."""

import os
import platform
import sys


def _get_clean_subprocess_env():
    """Get a clean environment for spawning system subprocesses.

    PyInstaller injects LD_LIBRARY_PATH (Linux) and DYLD_LIBRARY_PATH /
    DYLD_FRAMEWORK_PATH (macOS) pointing to its bundled libraries.  Child
    processes such as xdg-open or open inherit these variables, which can
    cause the system PDF viewer or browser to load incompatible libraries
    and fail silently.

    PyInstaller stores the original values as ``*_ORIG`` environment
    variables.  This function restores them so that child processes see
    the user's original library paths.

    Returns:
        A cleaned copy of ``os.environ``, or ``None`` if no cleaning is
        needed (unfrozen environment or Windows).
    """
    if not getattr(sys, 'frozen', False):
        return None

    system = platform.system()
    if system == 'Windows':
        return None

    env = os.environ.copy()

    if system == 'Linux':
        vars_to_clean = ['LD_LIBRARY_PATH']
    elif system == 'Darwin':
        vars_to_clean = ['DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH']
    else:
        return None

    for var in vars_to_clean:
        orig_key = f'{var}_ORIG'
        if orig_key in env:
            orig_value = env[orig_key]
            if orig_value:
                env[var] = orig_value
            else:
                env.pop(var, None)
            env.pop(orig_key, None)
        elif var in env:
            # No _ORIG means it was not set before PyInstaller — remove
            env.pop(var, None)

    return env
