"""
Legacy constants and utilities for NyaaTools migration.

This file contains old custom property keys that were used in v1.x.
They're only needed for:
1. Migration operator (upgrading old projects to v2)
2. Old operators that haven't been migrated yet

Once all operators are migrated to use PropertyGroups, this file can be deleted.
"""

# Legacy custom property keys (v1.x system)
PROP_AVATAR_NAME = "avatar_name"
PROP_AVATAR_EXPORT_PATH = "avatar_export_path"
PROP_AVATAR_LAYERS = "avatar_layers"
