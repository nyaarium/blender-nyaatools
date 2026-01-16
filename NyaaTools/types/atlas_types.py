"""
Atlas PropertyGroup definitions for persistence.

Stores atlas configuration on assets via Blender's property system,
enabling undo support and .blend file persistence.

NyaaAtlasIsland: Individual UV island configuration
NyaaAtlasMaterial: Material placement in the atlas
NyaaAtlasConfig: Complete atlas configuration (stored on NyaaAssetConfig)
"""

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)


# Resolution options (shared with bake)
ATLAS_RESOLUTION_ITEMS = [
    ("16384", "16384", "16384 pixels"),
    ("8192", "8192", "8192 pixels"),
    ("4096", "4096", "4096 pixels"),
    ("2048", "2048", "2048 pixels"),
    ("1024", "1024", "1024 pixels"),
    ("512", "512", "512 pixels"),
    ("256", "256", "256 pixels"),
]


class NyaaAtlasIsland(bpy.types.PropertyGroup):
    """
    Individual UV island configuration within a material.
    
    Stores island identity and local positioning within the parent
    material's tile. Used for fine-grained UV control.
    """
    
    island_id: StringProperty(
        name="Island ID",
        default="",
        description="Unique identifier for this island",
    )
    
    mesh_name: StringProperty(
        name="Mesh Name",
        default="",
        description="Name of the source mesh object",
    )
    
    # Local positioning within material's tile (0-1 relative)
    local_offset: FloatVectorProperty(
        name="Local Offset",
        size=2,
        default=(0.0, 0.0),
        min=0.0,
        max=1.0,
        description="Offset within parent tile",
    )
    
    local_scale: FloatVectorProperty(
        name="Local Scale",
        size=2,
        default=(1.0, 1.0),
        min=0.01,
        max=1.0,
        description="Scale within parent tile",
    )
    
    # Cached metrics
    uv_area: FloatProperty(
        name="UV Area",
        default=0.0,
        description="Total UV space area",
    )
    
    world_area: FloatProperty(
        name="World Area",
        default=0.0,
        description="Total world space surface area",
    )
    
    significance: FloatProperty(
        name="Significance",
        default=0.0,
        min=0.0,
        max=1.0,
        description="Weight for auto-placement",
    )


class NyaaAtlasMaterial(bpy.types.PropertyGroup):
    """
    Material placement configuration in the atlas.
    
    Defines which stratum and tile a material occupies.
    """
    
    material_name: StringProperty(
        name="Material",
        default="",
        description="Name of the material",
    )
    
    # Stratum placement
    stratum: IntProperty(
        name="Stratum",
        default=0,
        min=0,
        max=8,
        description="Mipmap level (0 = full, higher = smaller)",
    )
    
    tile_x: IntProperty(
        name="Tile X",
        default=0,
        min=0,
        description="X position in stratum grid",
    )
    
    tile_y: IntProperty(
        name="Tile Y",
        default=0,
        min=0,
        description="Y position in stratum grid",
    )
    
    # Auto-placement flag
    auto_stratum: BoolProperty(
        name="Auto Stratum",
        default=True,
        description="Automatically calculate stratum from texel density",
    )
    
    # Cached recommended stratum
    recommended_stratum: IntProperty(
        name="Recommended Stratum",
        default=0,
        min=0,
        max=8,
        description="Auto-calculated optimal stratum",
    )
    
    # Cached metrics
    total_uv_area: FloatProperty(
        name="Total UV Area",
        default=0.0,
        description="Aggregate UV space area",
    )
    
    total_world_area: FloatProperty(
        name="Total World Area",
        default=0.0,
        description="Aggregate world space surface area",
    )
    
    significance: FloatProperty(
        name="Significance",
        default=0.0,
        min=0.0,
        max=1.0,
        description="Texel density significance score",
    )
    
    # Islands (optional fine-grained control)
    islands: CollectionProperty(
        type=NyaaAtlasIsland,
        name="Islands",
        description="UV islands within this material",
    )
    
    active_island_index: IntProperty(
        name="Active Island",
        default=0,
    )
    
    # UI state
    expanded: BoolProperty(
        name="Expanded",
        default=False,
        description="Expand material details in UI",
    )


class NyaaAtlasConfig(bpy.types.PropertyGroup):
    """
    Complete atlas configuration for an asset.
    
    Stored on NyaaAssetConfig to persist with the asset.
    """
    
    # Enable atlas system
    enabled: BoolProperty(
        name="Atlas Enabled",
        default=False,
        description="Enable atlas-based texture packing",
    )
    
    # Resolution
    atlas_width: EnumProperty(
        name="Width",
        items=ATLAS_RESOLUTION_ITEMS,
        default="4096",
        description="Atlas texture width",
    )
    
    atlas_height: EnumProperty(
        name="Height",
        items=ATLAS_RESOLUTION_ITEMS,
        default="4096",
        description="Atlas texture height",
    )
    
    # Maximum stratum depth
    max_stratum: IntProperty(
        name="Max Stratum",
        default=4,
        min=1,
        max=8,
        description="Maximum stratum depth (4 = 16x16 grid)",
    )
    
    # Materials
    materials: CollectionProperty(
        type=NyaaAtlasMaterial,
        name="Materials",
        description="Material atlas configurations",
    )
    
    active_material_index: IntProperty(
        name="Active Material",
        default=0,
    )
    
    # Validation state (computed, not stored)
    has_overlaps: BoolProperty(
        name="Has Overlaps",
        default=False,
        description="Whether any materials overlap",
        options={"SKIP_SAVE"},
    )
    
    coverage: FloatProperty(
        name="Coverage",
        default=0.0,
        min=0.0,
        max=1.0,
        description="Fraction of atlas space used",
        options={"SKIP_SAVE"},
    )
    
    # UI state
    show_advanced: BoolProperty(
        name="Show Advanced",
        default=False,
        description="Show advanced atlas settings",
    )


# =============================================================================
# Registration
# =============================================================================


_classes = [
    NyaaAtlasIsland,
    NyaaAtlasMaterial,
    NyaaAtlasConfig,
]


def register():
    """Register atlas property types."""
    for cls in _classes:
        bpy.utils.register_class(cls)
    
    # Add atlas_config to NyaaAssetConfig after all classes are registered
    # This avoids circular dependency issues
    from .asset_types import NyaaAssetConfig
    from bpy.props import PointerProperty
    
    NyaaAssetConfig.atlas_config = PointerProperty(
        type=NyaaAtlasConfig,
        name="Atlas Config",
        description="Atlas texture packing configuration",
    )


def unregister():
    """Unregister atlas property types."""
    # Remove atlas_config from NyaaAssetConfig
    from .asset_types import NyaaAssetConfig
    
    if hasattr(NyaaAssetConfig, "atlas_config"):
        del NyaaAssetConfig.atlas_config
    
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)

