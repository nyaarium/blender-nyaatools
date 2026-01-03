"""
NyaaTools Panel - Unified Asset System.

Uses native Blender subpanels for collapsible sections.

Core Rule: The config host IS the asset identity:
- Has armature? Config lives on the Armature. Select armature to see asset.
- No armature? Config lives on the Mesh. Select mesh to see asset.

This file serves as the entry point and registration for all panel-related modules.
"""

import bpy

from .panels_uilists import UILIST_CLASSES
from .operators_asset import ASSET_OPERATOR_CLASSES
from .operators_export import EXPORT_OPERATOR_CLASSES
from .operators_bake import BAKE_OPERATOR_CLASSES
from .operators_migrate import MIGRATE_OPERATOR_CLASSES
from .panels_main import PANEL_CLASSES


# =============================================================================
# Registration
# =============================================================================

CLASSES = (
    UILIST_CLASSES
    + ASSET_OPERATOR_CLASSES
    + EXPORT_OPERATOR_CLASSES
    + BAKE_OPERATOR_CLASSES
    + MIGRATE_OPERATOR_CLASSES
    + PANEL_CLASSES
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
