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


