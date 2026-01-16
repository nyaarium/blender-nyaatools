"""
Atlas System - Usage Examples and API Reference

This module provides examples of how to use the atlas system.
Not intended to be imported directly - reference only.

The atlas system enables texture atlasing with stratum-based placement,
where materials can be assigned to different resolution tiers (stratums)
within a single combined atlas texture.
"""

# =============================================================================
# BASIC CONCEPTS
# =============================================================================
#
# Stratum: A mipmap-level tier in the atlas grid
#   - Stratum 0: Full atlas (1x1 grid, scale 1.0)
#   - Stratum 1: Half size (2x2 grid, scale 0.5, 4 tiles)
#   - Stratum 2: Quarter size (4x4 grid, scale 0.25, 16 tiles)
#   - Stratum N: 2^N x 2^N grid, scale 1/2^N
#
# Tile: A position within a stratum grid (tile_x, tile_y)
#
# Atlas UV Layer: "-- Atlas" UV layer stores transformed coordinates
#   (automatically deleted on export due to "--" prefix)
#
# =============================================================================


def example_stratum_math():
    """Example: Basic stratum calculations."""
    from NyaaTools.atlas.stratum import (
        stratum_to_grid_size,
        stratum_to_scale,
        tile_to_uv_offset,
        get_tile_bounds,
        promote_tile_coords,
        demote_tile_coords,
    )
    
    # Stratum 0: Full atlas
    assert stratum_to_grid_size(0) == 1  # 1x1 grid
    assert stratum_to_scale(0) == 1.0     # Full scale
    
    # Stratum 2: Quarter size materials
    assert stratum_to_grid_size(2) == 4  # 4x4 grid = 16 tiles
    assert stratum_to_scale(2) == 0.25    # Quarter scale
    
    # Tile position -> UV offset
    offset = tile_to_uv_offset(stratum=2, tile_x=1, tile_y=2)
    # Result: (0.25, 0.5) - tile at position (1,2) in a 4x4 grid
    
    # Get full tile bounds
    bounds = get_tile_bounds(stratum=2, tile_x=1, tile_y=2)
    # Result: ((0.25, 0.5), (0.5, 0.75))
    
    # Promote: Move to higher resolution (larger tile)
    new_stratum, new_tx, new_ty = promote_tile_coords(
        current_stratum=2, tile_x=2, tile_y=2
    )
    # Result: (1, 1, 1) - promoted from stratum 2 to stratum 1
    
    # Demote: Move to lower resolution (smaller tile)
    new_stratum, new_tx, new_ty = demote_tile_coords(
        current_stratum=1, tile_x=1, tile_y=1
    )
    # Result: (2, 2, 2) - demoted from stratum 1 to stratum 2


def example_build_descriptors():
    """Example: Building material descriptors from meshes."""    
    import bpy
    from NyaaTools.atlas.descriptors import (
        build_material_descriptors,
        build_atlas_descriptor,
    )
    
    # Get meshes to analyze
    meshes = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]    
    # Build descriptors for all materials
    descriptors = build_material_descriptors(
        meshes,
        atlas_resolution=4096,
        build_islands=True,  # Also detect UV islands
    )    
    # Each descriptor contains:
    for mat_name, desc in descriptors.items():
        print(f"Material: {mat_name}")
        print(f"  Recommended stratum: {desc.recommended_stratum}")
        print(f"  UV area: {desc.total_uv_area}")
        print(f"  World area: {desc.total_world_area}")
        print(f"  Significance: {desc.significance}")
        print(f"  Islands: {len(desc.islands)}")
    
    # Build a full atlas descriptor
    atlas = build_atlas_descriptor(
        meshes,
        atlas_width=4096,
        atlas_height=4096,
        asset_name="MyAsset",
        auto_place=True,  # Auto-assign stratum positions
    )

def example_stratum_grid():
    """Example: Managing tile occupancy with StratumGrid."""
    from NyaaTools.atlas.stratum import StratumGrid
    
    grid = StratumGrid(max_stratum=4)
    
    # Occupy a tile at stratum 1
    success = grid.occupy_tile(stratum=1, tile_x=0, tile_y=0)
    # This tile covers UV space (0,0) to (0.5, 0.5)
    
    # Check if overlapping tiles are free
    # A tile at stratum 2 position (0,0) would overlap!
    is_free = grid.is_tile_free(stratum=2, tile_x=0, tile_y=0)
    # Result: False - overlaps with stratum 1 tile
    
    # But stratum 2 position (2,0) is free
    is_free = grid.is_tile_free(stratum=2, tile_x=2, tile_y=0)
    # Result: True - no overlap
    
    # Find first free tile at stratum 2
    free_tile = grid.find_free_tile(stratum=2)
    # Result: (2, 0) or similar
    
    # Calculate coverage
    coverage = grid.calculate_coverage()
    # Result: 0.25 (stratum 1 tile = 25% of atlas)


def example_material_promote_demote():
    """Example: Promoting/demoting materials with validation."""
    from NyaaTools.atlas.descriptors import MaterialDescriptor
    from NyaaTools.atlas.stratum import StratumGrid
    
    grid = StratumGrid(max_stratum=4)
    
    # Create a material descriptor
    material = MaterialDescriptor(
        material_name="Skin",
        source_mesh_names=["Body", "Face"],
        stratum=2,
        tile_x=0,
        tile_y=0,
    )
    
    # Occupy its tile
    grid.occupy_tile(material.stratum, material.tile_x, material.tile_y)
    
    # Promote to higher resolution
    success = material.promote(grid=grid)
    if success:
        print(f"Promoted to stratum {material.stratum}")
        # Now at stratum 1, tile (0, 0)
    
    # Demote back
    success = material.demote(grid=grid)
    if success:
        print(f"Demoted to stratum {material.stratum}")


def example_apply_uv_transforms():
    """Example: Applying atlas UV transforms to meshes."""    
    import bpy
    from NyaaTools.atlas.recombine import (
        copy_uvs_to_atlas_layer,
        transform_atlas_uvs_for_material,
        ATLAS_UV_NAME,
    )
    
    mesh = bpy.context.active_object    
    # Create atlas UV layer (copies from UVMap)
    copy_success = copy_uvs_to_atlas_layer(mesh, source_uv_name="UVMap")    
    # Transform UVs for a material to its atlas position
    transform_success = transform_atlas_uvs_for_material(
        mesh=mesh,
        material_name="Skin",
        stratum=2,      # Quarter size
        tile_x=1,       # Position (1, 2) in 4x4 grid
        tile_y=2,
        debug_print=print,
    )    # All faces using "Skin" material now have UVs in (0.25, 0.5) to (0.5, 0.75)


def example_island_detection():
    """Example: Detecting UV islands."""
    import bpy
    from NyaaTools.atlas.island_detection import (
        detect_uv_islands,
        get_island_count,
        get_island_bounds,
    )
    
    mesh = bpy.context.active_object
    
    # Detect all islands
    islands = detect_uv_islands(mesh, uv_layer_name="UVMap")
    
    for i, island in enumerate(islands):
        print(f"Island {i}:")
        print(f"  Faces: {len(island['face_indices'])}")
        print(f"  Bounds: {island['bounds_min']} - {island['bounds_max']}")
        print(f"  UV Area: {island['uv_area']}")
        print(f"  World Area: {island['world_area']}")
    
    # Filter by material
    islands = detect_uv_islands(mesh, material_filter="Skin")


def example_repack_uvs():
    """Example: Repacking UV islands."""
    import bpy
    from NyaaTools.atlas.repack_helper import (
        pack_islands,
        pack_to_tile,
        PackMethod,
        is_uvpackmaster_available,
    )
    
    mesh = bpy.context.active_object
    
    # Pack using built-in packer
    pack_islands(
        mesh,
        uv_layer_name="UVMap",
        method=PackMethod.MINIMUM_STRETCH,
        margin=0.001,
        rotate=True,
    )
    
    # Or use UVPackMaster if available
    if is_uvpackmaster_available():
        pack_islands(
            mesh,
            method=PackMethod.UVPACKMASTER,
            margin=0.001,
        )
    
    # Pack to a specific tile
    pack_to_tile(
        mesh,
        uv_layer_name="-- Atlas",
        tile_min=(0.25, 0.5),
        tile_max=(0.5, 0.75),
    )


def example_full_recombination():
    """Example: Full atlas recombination workflow."""    
    import bpy
    from NyaaTools.atlas.descriptors import build_atlas_descriptor
    from NyaaTools.atlas.capture_bake import capture_material_bakes
    from NyaaTools.atlas.recombine import (
        apply_atlas_transforms,
        execute_atlas_recombination,
    )
    
    # Get asset meshes
    meshes = [bpy.data.objects["Body"], bpy.data.objects["Face"]]    
    # Build atlas configuration
    atlas = build_atlas_descriptor(
        meshes,
        atlas_width=4096,
        atlas_height=4096,
        asset_name="Character",
        auto_place=True,
    )    
    # Optionally adjust placements
    if "Skin" in atlas.materials:
        atlas.materials["Skin"].stratum = 1  # Force larger tile
        atlas.materials["Skin"].tile_x = 0
        atlas.materials["Skin"].tile_y = 0
    
    # Capture material bakes (intermediate textures)
    captured = capture_material_bakes(
        atlas,
        bake_formats=["rgb"],
        resolution=(512, 512),
        debug_print=print,
    )
    
    # Execute full recombination and final bake
    results = execute_atlas_recombination(
        atlas,
        bake_formats=["rgb"],
        output_resolution=(512, 512),
        debug_print=print,
    )    # Results: {"rgba": <Image>, "normalgl": <Image>}


def example_operator_usage():
    """Example: Using atlas operators."""
    import bpy
    
    # Refresh materials from asset
    bpy.ops.nyaa.atlas_refresh_materials()
    
    # Promote a material to higher resolution
    bpy.ops.nyaa.atlas_promote_stratum(material_name="Skin")
    
    # Demote a material to lower resolution
    bpy.ops.nyaa.atlas_demote_stratum(material_name="Hair")
    
    # Move material to specific tile
    bpy.ops.nyaa.atlas_move_tile(
        material_name="Eyes",
        target_stratum=3,
        target_tile_x=4,
        target_tile_y=0,
    )
    
    # Auto-place all materials
    bpy.ops.nyaa.atlas_auto_place(use_recommended=True)
    
    # Validate configuration
    bpy.ops.nyaa.atlas_validate()
    
    # Apply atlas UV transforms
    bpy.ops.nyaa.atlas_apply_transforms()
    
    # Execute full recombination
    bpy.ops.nyaa.atlas_execute_recombination()


# =============================================================================
# PROPERTY GROUP STRUCTURE
# =============================================================================
#
# NyaaAssetConfig
#   └── atlas_config: NyaaAtlasConfig
#         ├── enabled: bool
#         ├── atlas_width: enum ("4096", "2048", etc.)
#         ├── atlas_height: enum
#         ├── max_stratum: int (default 4)
#         ├── materials: CollectionProperty[NyaaAtlasMaterial]
#         │     ├── material_name: str
#         │     ├── stratum: int
#         │     ├── tile_x: int
#         │     ├── tile_y: int
#         │     ├── auto_stratum: bool
#         │     ├── recommended_stratum: int
#         │     ├── significance: float
#         │     └── islands: CollectionProperty[NyaaAtlasIsland]
#         │           ├── island_id: str
#         │           ├── mesh_name: str
#         │           ├── local_offset: float[2]
#         │           ├── local_scale: float[2]
#         │           └── significance: float
#         ├── has_overlaps: bool (computed)
#         └── coverage: float (computed)
#
# =============================================================================
