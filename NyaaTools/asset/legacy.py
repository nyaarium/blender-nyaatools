"""
Legacy constants and utilities for NyaaTools migration.

This file contains old custom property keys that were used in v1.x.
They're only needed for:
1. Migration operator (upgrading old projects to v2)
2. Old operators that haven't been migrated yet

Once all operators are migrated to use PropertyGroups, this file can be deleted.
"""

import bpy

# Legacy custom property keys (v1.x system)
PROP_AVATAR_NAME = "avatar_name"
PROP_AVATAR_EXPORT_PATH = "avatar_export_path"
PROP_AVATAR_LAYERS = "avatar_layers"


def has_legacy_avatar_data(obj) -> bool:
    """Check if an object has legacy NyaaTools custom properties."""
    if obj is None:
        return False
    if PROP_AVATAR_NAME in obj:
        return True
    if PROP_AVATAR_EXPORT_PATH in obj:
        return True
    if PROP_AVATAR_LAYERS in obj:
        return True
    return False


def scene_has_legacy_data(context) -> bool:
    """Check if any object in scene has legacy data."""
    for obj in bpy.data.objects:
        if has_legacy_avatar_data(obj):
            return True
    return False
