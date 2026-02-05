"""
Modifier application for asset export.
"""

import bpy

from .list_asset_armatures import list_asset_armatures
from ..operators.ApplyModifierShapeKeysViaUV import apply_modifiers_with_shape_keys
from ..common.deselect_all import deselect_all
from ..common.selection_add import selection_add


def apply_export_modifiers(obj):
    """
    Apply or remove modifiers in preparation for export.

    - Removes internal modifiers (prefixed with "--")
    - Removes MToon outline modifiers
    - Removes armature modifiers targeting assets (will be reconfigured)
    - Applies all other modifiers (with shape key support)
    - Applies transforms
    """
    if obj is None:
        raise BaseException(
            "apply_export_modifiers() :: Expected a mesh object, got: None"
        )

    selection_add(obj)

    asset_names = list_asset_armatures()

    for modifier in obj.modifiers:
        if modifier.name.startswith("--"):
            # Internal use only - remove
            bpy.ops.object.modifier_remove(modifier=modifier.name)
        elif modifier.name.startswith("MToon"):
            # MToon outline modifier - remove
            bpy.ops.object.modifier_remove(modifier=modifier.name)
        elif modifier.type == "ARMATURE":
            # Remove armature modifiers that target assets (will be reconfigured)
            # Otherwise apply it
            if modifier.object is None:
                bpy.ops.object.modifier_remove(modifier=modifier.name)
                continue

            armature = modifier.object

            if armature.name in asset_names:
                bpy.ops.object.modifier_remove(modifier=modifier.name)
            else:
                apply_modifiers_with_shape_keys(bpy.context, [modifier.name], False)
        else:
            apply_modifiers_with_shape_keys(bpy.context, [modifier.name], False)

    try:
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    except:
        pass

    deselect_all()
