"""
NyaaTools persistent settings.

Stored on Scene for per-file persistence.
"""

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)


class NyaaToolsBakeSettings(bpy.types.PropertyGroup):
    """Settings for texture baking operations."""

    resolution: EnumProperty(
        name="Resolution",
        items=[
            ("512", "512", "512x512 pixels"),
            ("1024", "1K", "1024x1024 pixels"),
            ("2048", "2K", "2048x2048 pixels"),
            ("4096", "4K", "4096x4096 pixels"),
        ],
        default="2048",
        description="Output texture resolution",
    )

    include_rgba: BoolProperty(
        name="RGBA (Base Color + Alpha)",
        default=True,
        description="Bake base color with alpha channel",
    )

    include_orm: BoolProperty(
        name="ME-SP-RO (Metallic/Specular/Roughness)",
        default=True,
        description="Bake metallic, specular, and roughness packed texture",
    )

    include_normal: BoolProperty(
        name="Normal Map",
        default=True,
        description="Bake normal map (OpenGL format)",
    )

    include_emission: BoolProperty(
        name="Emission",
        default=True,
        description="Bake emission texture",
    )


class NyaaToolsExportSettings(bpy.types.PropertyGroup):
    """Settings for asset export operations."""

    format: EnumProperty(
        name="Format",
        items=[
            ("fbx", "FBX", "Export as FBX (Unity/Unreal)"),
            ("obj", "OBJ", "Export as OBJ (static mesh)"),
            ("votv", "VotV", "Export for Voices of the Void"),
        ],
        default="fbx",
        description="Export file format",
    )


class NyaaToolsSettings(bpy.types.PropertyGroup):
    """Main settings container for NyaaTools."""

    bake: PointerProperty(type=NyaaToolsBakeSettings)
    export: PointerProperty(type=NyaaToolsExportSettings)


