"""
UV repacking helpers.

Provides helpers for repacking UV islands using:
- Blender's built-in "Pack Islands" (Minimum Stretch)
- UVPackMaster addon (if installed)

These are non-automatic helpers intended for future UV tools integration.
"""

from __future__ import annotations
from typing import List, Optional, Callable, Tuple, Dict, Any
from enum import Enum
import bpy


class PackMethod(Enum):
    """UV packing method options."""
    MINIMUM_STRETCH = "minimum_stretch"
    UVPACKMASTER = "uvpackmaster"


def is_uvpackmaster_available() -> bool:
    """
    Check if UVPackMaster addon is installed and enabled.
    
    Returns:
        True if UVPackMaster is available
    """
    return "uvpackmaster3" in bpy.context.preferences.addons


def get_available_pack_methods() -> List[PackMethod]:
    """
    Get list of available packing methods.
    
    Returns:
        List of available PackMethod options
    """
    methods = [PackMethod.MINIMUM_STRETCH]
    
    if is_uvpackmaster_available():
        methods.append(PackMethod.UVPACKMASTER)
    
    return methods


def pack_islands_minimum_stretch(
    mesh: bpy.types.Object,
    uv_layer_name: str = "UVMap",
    margin: float = 0.001,
    rotate: bool = True,
    debug_print: Optional[Callable[..., None]] = None,
) -> bool:
    """
    Pack UV islands using Blender's built-in Pack Islands operator.
    
    Uses the "Minimum Stretch" algorithm built into Blender.
    
    Args:
        mesh: The mesh object
        uv_layer_name: UV layer to pack
        margin: Margin between islands (UV space)
        rotate: Allow rotation for better packing
        debug_print: Optional debug function
        
    Returns:
        True if successful
    """
    if debug_print is None:
        def debug_print(*args):
            pass
    
    if mesh.type != "MESH":
        debug_print("⚠️ Object is not a mesh")
        return False
    
    if uv_layer_name not in mesh.data.uv_layers:
        debug_print(f"⚠️ UV layer '{uv_layer_name}' not found")
        return False
    
    # Store current state
    original_active = bpy.context.view_layer.objects.active
    original_mode = bpy.context.mode
    original_selected = [obj for obj in bpy.context.selected_objects]
    
    try:
        # Select and activate mesh
        bpy.ops.object.select_all(action="DESELECT")
        mesh.select_set(True)
        bpy.context.view_layer.objects.active = mesh
        
        # Set active UV layer
        mesh.data.uv_layers.active = mesh.data.uv_layers[uv_layer_name]
        
        # Enter edit mode
        bpy.ops.object.mode_set(mode="EDIT")
        
        # Select all faces
        bpy.ops.mesh.select_all(action="SELECT")
        
        # Pack islands
        bpy.ops.uv.pack_islands(margin=margin, rotate=rotate)
        
        debug_print(f"✅ Packed islands on '{mesh.name}' (margin={margin}, rotate={rotate})")
        return True
        
    except Exception as e:
        debug_print(f"⚠️ Pack failed: {e}")
        return False
        
    finally:
        # Restore state
        bpy.ops.object.mode_set(mode="OBJECT")
        
        bpy.ops.object.select_all(action="DESELECT")
        for obj in original_selected:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        
        if original_active and original_active.name in bpy.data.objects:
            bpy.context.view_layer.objects.active = original_active
        
        if original_mode == "EDIT":
            bpy.ops.object.mode_set(mode="EDIT")


def pack_islands_uvpackmaster(
    mesh: bpy.types.Object,
    uv_layer_name: str = "UVMap",
    margin: float = 0.001,
    rotation_step: int = 90,
    debug_print: Optional[Callable[..., None]] = None,
) -> bool:
    """
    Pack UV islands using UVPackMaster addon.
    
    Requires UVPackMaster to be installed and enabled.
    
    Args:
        mesh: The mesh object
        uv_layer_name: UV layer to pack
        margin: Margin between islands (UV space)
        rotation_step: Rotation step in degrees (0 to disable)
        debug_print: Optional debug function
        
    Returns:
        True if successful
    """
    if debug_print is None:
        def debug_print(*args):
            pass
    
    if not is_uvpackmaster_available():
        debug_print("⚠️ UVPackMaster is not available")
        return False
    
    if mesh.type != "MESH":
        debug_print("⚠️ Object is not a mesh")
        return False
    
    if uv_layer_name not in mesh.data.uv_layers:
        debug_print(f"⚠️ UV layer '{uv_layer_name}' not found")
        return False
    
    # Store current state
    original_active = bpy.context.view_layer.objects.active
    original_mode = bpy.context.mode
    original_selected = [obj for obj in bpy.context.selected_objects]
    
    try:
        # Select and activate mesh
        bpy.ops.object.select_all(action="DESELECT")
        mesh.select_set(True)
        bpy.context.view_layer.objects.active = mesh
        
        # Set active UV layer
        mesh.data.uv_layers.active = mesh.data.uv_layers[uv_layer_name]
        
        # Enter edit mode
        bpy.ops.object.mode_set(mode="EDIT")
        
        # Select all faces
        bpy.ops.mesh.select_all(action="SELECT")
        
        # UVPackMaster pack operation
        # Note: Operator name may vary by version
        try:
            bpy.ops.uvpackmaster3.pack(
                margin=margin,
                rotation_step=rotation_step,
            )
        except AttributeError:
            # Try alternative operator name
            bpy.ops.uvpackmaster.pack(
                margin=margin,
                rotation_step=rotation_step,
            )
        
        debug_print(f"✅ UVPackMaster packed '{mesh.name}'")
        return True
        
    except Exception as e:
        debug_print(f"⚠️ UVPackMaster pack failed: {e}")
        return False
        
    finally:
        # Restore state
        bpy.ops.object.mode_set(mode="OBJECT")
        
        bpy.ops.object.select_all(action="DESELECT")
        for obj in original_selected:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        
        if original_active and original_active.name in bpy.data.objects:
            bpy.context.view_layer.objects.active = original_active
        
        if original_mode == "EDIT":
            bpy.ops.object.mode_set(mode="EDIT")


def pack_islands(
    mesh: bpy.types.Object,
    uv_layer_name: str = "UVMap",
    method: PackMethod = PackMethod.MINIMUM_STRETCH,
    margin: float = 0.001,
    rotate: bool = True,
    debug_print: Optional[Callable[..., None]] = None,
) -> bool:
    """
    Pack UV islands using the specified method.
    
    Convenience wrapper that dispatches to the appropriate packer.
    
    Args:
        mesh: The mesh object
        uv_layer_name: UV layer to pack
        method: Packing method to use
        margin: Margin between islands
        rotate: Allow rotation (for built-in packer)
        debug_print: Optional debug function
        
    Returns:
        True if successful
    """
    if method == PackMethod.UVPACKMASTER:
        rotation_step = 90 if rotate else 0
        return pack_islands_uvpackmaster(
            mesh, uv_layer_name, margin, rotation_step, debug_print
        )
    else:
        return pack_islands_minimum_stretch(
            mesh, uv_layer_name, margin, rotate, debug_print
        )


def pack_to_tile(
    mesh: bpy.types.Object,
    uv_layer_name: str = "UVMap",
    tile_min: Tuple[float, float] = (0.0, 0.0),
    tile_max: Tuple[float, float] = (1.0, 1.0),
    method: PackMethod = PackMethod.MINIMUM_STRETCH,
    margin: float = 0.001,
    debug_print: Optional[Callable[..., None]] = None,
) -> bool:
    """
    Pack UV islands and scale to fit within a specific tile.
    
    First packs to 0-1 space, then transforms to target tile.
    
    Args:
        mesh: The mesh object
        uv_layer_name: UV layer to pack
        tile_min: Target tile minimum (u, v)
        tile_max: Target tile maximum (u, v)
        method: Packing method
        margin: Margin between islands
        debug_print: Optional debug function
        
    Returns:
        True if successful
    """
    if debug_print is None:
        def debug_print(*args):
            pass
    
    # First pack to 0-1 space
    if not pack_islands(mesh, uv_layer_name, method, margin, True, debug_print):
        return False
    
    # Then transform to target tile
    if tile_min == (0.0, 0.0) and tile_max == (1.0, 1.0):
        return True  # No transform needed
    
    # Import transform function
    from .atlas_transform import transform_uv_layer
    
    scale = (
        tile_max[0] - tile_min[0],
        tile_max[1] - tile_min[1],
    )
    offset = tile_min
    
    transform_uv_layer(mesh, uv_layer_name, scale, offset)
    debug_print(f"    Transformed to tile {tile_min} - {tile_max}")
    
    return True


def estimate_packing_efficiency(
    mesh: bpy.types.Object,
    uv_layer_name: str = "UVMap",
) -> float:
    """
    Estimate the packing efficiency of current UVs.
    
    Efficiency = (total UV area) / (bounding box area)
    
    Args:
        mesh: The mesh object
        uv_layer_name: UV layer to analyze
        
    Returns:
        Packing efficiency (0.0 to 1.0)
    """
    if mesh.type != "MESH":
        return 0.0
    
    if uv_layer_name not in mesh.data.uv_layers:
        return 0.0
    
    uv_layer = mesh.data.uv_layers[uv_layer_name]
    
    # Collect all UVs
    u_coords = []
    v_coords = []
    total_uv_area = 0.0
    
    for poly in mesh.data.polygons:
        uvs = [uv_layer.data[loop_idx].uv for loop_idx in poly.loop_indices]
        
        for uv in uvs:
            u_coords.append(uv[0])
            v_coords.append(uv[1])
        
        # Calculate face UV area
        n = len(uvs)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += uvs[i][0] * uvs[j][1]
            area -= uvs[j][0] * uvs[i][1]
        total_uv_area += abs(area) / 2.0
    
    if not u_coords:
        return 0.0
    
    # Bounding box area
    bbox_width = max(u_coords) - min(u_coords)
    bbox_height = max(v_coords) - min(v_coords)
    bbox_area = bbox_width * bbox_height
    
    if bbox_area <= 0:
        return 0.0
    
    return min(total_uv_area / bbox_area, 1.0)
