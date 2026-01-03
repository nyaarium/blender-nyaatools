"""
Prop PropertyGroup definitions.

NyaaPropConfig: Prop/static mesh configuration stored on Mesh objects
"""

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    PointerProperty,
    StringProperty,
)


class NyaaPropConfig(bpy.types.PropertyGroup):
    """Prop/static mesh configuration stored on Mesh objects."""

    is_prop: BoolProperty(
        name="Is Prop",
        default=False,
        description="Mark this mesh as a managed prop",
    )
    prop_name: StringProperty(
        name="Prop Name",
        default="",
        description="Display name for this prop",
    )
    export_path: StringProperty(
        name="Export Path",
        default="",
        subtype="FILE_PATH",
        description="Path to export this prop",
    )


CLASSES = [
    NyaaPropConfig,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)

    # Attach to Object type
    bpy.types.Object.nyaa_prop = PointerProperty(type=NyaaPropConfig)


def unregister():
    if hasattr(bpy.types.Object, "nyaa_prop"):
        del bpy.types.Object.nyaa_prop

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
