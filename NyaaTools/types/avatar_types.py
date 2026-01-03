"""
Avatar PropertyGroup definitions.

NyaaAvatarMeshEntry: Individual mesh entry in an avatar's mesh list
NyaaExportProfile: Export configuration (path + format)
NyaaAvatarConfig: Avatar configuration stored on Armature objects
"""

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)


class NyaaAvatarMeshEntry(bpy.types.PropertyGroup):
    """A mesh assigned to an avatar with its layer name."""

    mesh_object: PointerProperty(
        name="Mesh",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == "MESH",
        description="Mesh to merge onto this avatar",
    )
    layer_name: StringProperty(
        name="Layer",
        default="Base",
        description="Layer to merge this mesh onto (Base, Outfit, Hair, etc)",
    )


# Resolution options for bake
BAKE_RESOLUTION_ITEMS = [
    ("16384", "16384", "16384 pixels"),
    ("8192", "8192", "8192 pixels"),
    ("4096", "4096", "4096 pixels"),
    ("2048", "2048", "2048 pixels"),
    ("1024", "1024", "1024 pixels"),
    ("512", "512", "512 pixels"),
    ("256", "256", "256 pixels"),
    ("128", "128", "128 pixels"),
    ("64", "64", "64 pixels"),
]

# Image type options
BAKE_IMAGE_TYPE_ITEMS = [
    ("png", "PNG", "8-bit PNG (good for color/diffuse)"),
    ("exr", "EXR", "32-bit EXR (best for linear/utility data)"),
]


class NyaaBakeImage(bpy.types.PropertyGroup):
    """One bake output image configuration."""

    # Name field commented out for first release - will use DTP format as filename
    # name: StringProperty(
    #     name="Name",
    #     default="",
    #     description="Output filename prefix (e.g., diffuse, pbr, normal)",
    # )
    format: StringProperty(
        name="Format",
        default="rgba",
        description="DTP format string (alias like 'rgba' or channels like 'me-sp-ro')",
    )
    image_type: EnumProperty(
        name="Type",
        items=BAKE_IMAGE_TYPE_ITEMS,
        default="png",
        description="Output image file format",
    )
    width: EnumProperty(
        name="Width",
        items=BAKE_RESOLUTION_ITEMS,
        default="4096",
        description="Output texture width",
    )
    height: EnumProperty(
        name="Height",
        items=BAKE_RESOLUTION_ITEMS,
        default="4096",
        description="Output texture height",
    )


class NyaaExportProfile(bpy.types.PropertyGroup):
    """Export configuration with path and format."""

    path: StringProperty(
        name="Path",
        default="",
        subtype="FILE_PATH",
        description="Export path (file or folder)",
    )
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


class NyaaAvatarConfig(bpy.types.PropertyGroup):
    """Avatar configuration stored on Armature objects."""

    is_avatar: BoolProperty(
        name="Is Avatar",
        default=False,
        description="Mark this armature as an avatar",
    )
    avatar_name: StringProperty(
        name="Avatar Name",
        default="",
        description="Display name for this avatar",
    )
    # Legacy field - kept for migration compatibility
    export_path: StringProperty(
        name="Export Path",
        default="",
        subtype="FILE_PATH",
        description="(Legacy) Path to export this avatar",
    )
    meshes: CollectionProperty(
        type=NyaaAvatarMeshEntry,
        name="Avatar Meshes",
        description="Meshes assigned to this avatar",
    )
    active_mesh_index: IntProperty(
        name="Active Mesh Index",
        default=0,
    )
    # New export profiles system
    export_profiles: CollectionProperty(
        type=NyaaExportProfile,
        name="Export Profiles",
        description="Export configurations for this avatar",
    )
    active_export_index: IntProperty(
        name="Active Export Index",
        default=0,
    )
    # Bake configuration
    bake_images: CollectionProperty(
        type=NyaaBakeImage,
        name="Bake Images",
        description="Image channel configurations for baking",
    )
    active_bake_index: IntProperty(
        name="Active Bake Index",
        default=0,
    )


# Registration order matters: dependencies first
CLASSES = [
    NyaaAvatarMeshEntry,
    NyaaExportProfile,
    NyaaBakeImage,
    NyaaAvatarConfig,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)

    # Attach to Object type (works for both Armatures and Meshes)
    bpy.types.Object.nyaa_avatar = PointerProperty(type=NyaaAvatarConfig)


def unregister():
    # Remove from Object type
    if hasattr(bpy.types.Object, "nyaa_avatar"):
        del bpy.types.Object.nyaa_avatar

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
