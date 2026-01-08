"""
Asset PropertyGroup definitions.

Unified asset system - the config host IS the asset identity:
- Has armature? Config lives on the Armature. Select armature to see asset.
- No armature? Config lives on the Mesh. Select mesh to see asset.

NyaaAssetMeshEntry: Individual mesh entry in an asset's mesh list
NyaaExportProfile: Export configuration (path + format)
NyaaAssetConfig: Asset configuration stored on Armature or Mesh objects
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


class NyaaAssetMeshEntry(bpy.types.PropertyGroup):
    """A mesh assigned to an asset with its layer name."""

    mesh_object: PointerProperty(
        name="Mesh",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == "MESH",
        description="Mesh to merge onto this asset",
    )
    layer_name: StringProperty(
        name="Layer",
        default="Base",
        description="Layer to merge this mesh onto (Base, Outfit, Hair, etc)",
    )
    is_ue_collider: BoolProperty(
        name="Unreal Engine Convex Collision",
        default=False,
        description="Mark as Unreal Engine convex-collision mesh (UCX_)",
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
    optimize_resolution: BoolProperty(
        name="Optimize",
        default=True,
        description="Auto-detect optimal resolution (use width/height as maximum cap)",
    )


class NyaaExportProfile(bpy.types.PropertyGroup):
    """Export configuration with path, format, and export options."""

    target_type: EnumProperty(
        name="Target",
        items=[
            ("file", "File", "Export to filesystem"),
            (
                "collection",
                "Collection",
                "Export to __Export__ collection as Blender asset",
            ),
        ],
        default="file",
        description="Export target type",
    )
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
    export_static: BoolProperty(
        name="Export as Static",
        default=False,
        description="Apply pose and modifiers, remove armature (exports as static mesh)",
    )
    bake_after_export: BoolProperty(
        name="Bake Textures",
        default=False,
        description="Auto-bake textures after export using configured bake profiles",
    )
    include_ue_colliders: BoolProperty(
        name="Include UE Colliders",
        default=False,
        description="Include Unreal Engine convex-collision meshes (UCX_) in export",
    )


class NyaaAssetConfig(bpy.types.PropertyGroup):
    """
    Asset configuration stored on Armature or Mesh objects.

    The host object type determines the asset type:
    - obj.type == "ARMATURE" and obj.nyaa_asset.is_asset -> Asset with armature
    - obj.type == "MESH" and obj.nyaa_asset.is_asset -> Static asset

    No armature_ref needed - if the config is on an Armature object, that's your armature.
    """

    is_asset: BoolProperty(
        name="Is Asset",
        default=False,
        description="Mark this object as an asset",
    )
    is_humanoid: BoolProperty(
        name="Is Humanoid",
        default=False,
        description="Cached humanoid detection (set on asset creation/migration)",
    )
    asset_name: StringProperty(
        name="Asset Name",
        default="",
        description="Display name for this asset",
    )
    meshes: CollectionProperty(
        type=NyaaAssetMeshEntry,
        name="Asset Meshes",
        description="Meshes assigned to this asset",
    )
    active_mesh_index: IntProperty(
        name="Active Mesh Index",
        default=0,
    )
    export_profiles: CollectionProperty(
        type=NyaaExportProfile,
        name="Export Profiles",
        description="Export configurations for this asset",
    )
    active_export_index: IntProperty(
        name="Active Export Index",
        default=0,
    )
    bake_images: CollectionProperty(
        type=NyaaBakeImage,
        name="Bake Images",
        description="Image channel configurations for baking",
    )
    active_bake_index: IntProperty(
        name="Active Bake Index",
        default=0,
    )
    show_bake_channels: BoolProperty(
        name="Show Bake Channels",
        description="Expand bake channels section",
        default=True,
    )
    show_export_profiles: BoolProperty(
        name="Show Export Profiles",
        description="Expand export profiles section",
        default=True,
    )


