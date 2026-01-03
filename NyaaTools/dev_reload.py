"""
Hot reload support for NyaaTools development.

Called from __init__.py register() to reload all submodules from disk.
This enables the "uncheck/recheck addon" workflow for development.

WARNING: PropertyGroup changes require a Blender restart.
WARNING: Renamed/deleted classes can leave garbage. Restart if weird issues occur.
"""

import importlib
import sys


def reload_submodules():
    """
    Reload all NyaaTools submodules from disk.

    Called from register() before imports to refresh module code.
    Modules are reloaded deepest-first to handle dependencies.
    """
    package = __package__  # "NyaaTools"
    prefix = package + "."

    # Collect all NyaaTools submodules (not this one, not the root)
    submodules = [
        name
        for name in sys.modules
        if name.startswith(prefix)
        if "dev_reload" not in name
    ]

    # Sort by depth (deepest first) so dependencies reload before dependents
    submodules.sort(key=lambda x: x.count("."), reverse=True)

    for name in submodules:
        module = sys.modules.get(name)
        if module is not None:
            try:
                importlib.reload(module)
            except Exception as e:
                print(f"Failed to reload {name}: {e}")
