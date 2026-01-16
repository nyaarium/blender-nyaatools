"""
Atlas UV transformation utilities.

Provides functions for transforming UVs between original and atlas space,
including per-material and per-island transforms.
"""

from __future__ import annotations
from typing import List, Optional, Callable, Tuple, Dict
import bpy
import bmesh


# UV layer name for atlas (-- prefix means deleted on export)
ATLAS_UV_NAME = "-- Atlas"


def ensure_atlas_uv_layer(mesh: bpy.types.Object) -> Optional[bpy.types.MeshUVLoopLayer]:
    """
    Ensure the atlas UV layer exists on a mesh.
    
    Creates the layer if it doesn't exist.
    
    Args:
        mesh: The mesh object
        
    Returns:
        The atlas UV layer, or None if mesh is invalid
    """
    if mesh.type != "MESH":
        return None
    
    if ATLAS_UV_NAME not in mesh.data.uv_layers:
        mesh.data.uv_layers.new(name=ATLAS_UV_NAME)
    
    return mesh.data.uv_layers[ATLAS_UV_NAME]


def remove_atlas_uv_layer(mesh: bpy.types.Object) -> bool:
    """
    Remove the atlas UV layer from a mesh.
    
    Args:
        mesh: The mesh object
        
    Returns:
        True if layer was removed, False if not found
    """
    if mesh.type != "MESH":
        return False
    
    if ATLAS_UV_NAME in mesh.data.uv_layers:
        mesh.data.uv_layers.remove(mesh.data.uv_layers[ATLAS_UV_NAME])
        return True
    
    return False


def copy_uv_layer(
    mesh: bpy.types.Object,
    source_name: str,
    dest_name: str,
) -> bool:
    """
    Copy UVs from one layer to another.
    
    Creates destination layer if it doesn't exist.
    
    Args:
        mesh: The mesh object
        source_name: Source UV layer name
        dest_name: Destination UV layer name
        
    Returns:
        True if successful
    """
    if mesh.type != "MESH":
        return False
    
    if source_name not in mesh.data.uv_layers:
        return False
    
    source_uv = mesh.data.uv_layers[source_name]
    
    # Create dest if needed
    if dest_name not in mesh.data.uv_layers:
        mesh.data.uv_layers.new(name=dest_name)
    
    dest_uv = mesh.data.uv_layers[dest_name]
    
    # Copy coordinates
    for i, loop_data in enumerate(source_uv.data):
        dest_uv.data[i].uv = loop_data.uv.copy()
    
    return True


def transform_uv_layer(
    mesh: bpy.types.Object,
    uv_layer_name: str,
    scale: Tuple[float, float],
    offset: Tuple[float, float],
    face_indices: Optional[List[int]] = None,
) -> int:
    """
    Apply scale and offset transform to UVs.
    
    new_uv = old_uv * scale + offset
    
    Args:
        mesh: The mesh object
        uv_layer_name: UV layer to transform
        scale: (scale_u, scale_v)
        offset: (offset_u, offset_v)
        face_indices: Optional list of face indices to transform.
                     If None, transforms all faces.
        
    Returns:
        Number of loops transformed
    """
    if mesh.type != "MESH":
        return 0
    
    if uv_layer_name not in mesh.data.uv_layers:
        return 0
    
    uv_layer = mesh.data.uv_layers[uv_layer_name]
    
    # Check if UV layer has data - if not, it's empty and we can't transform
    if len(uv_layer.data) == 0:
        return 0
    
    # Build set of loop indices to transform
    if face_indices is not None:
        loop_indices = set()
        for poly in mesh.data.polygons:
            if poly.index in face_indices:
                loop_indices.update(poly.loop_indices)
    else:
        loop_indices = set(range(len(uv_layer.data)))
    
    # Filter out invalid indices (bounds check)
    valid_loop_indices = [idx for idx in loop_indices if 0 <= idx < len(uv_layer.data)]
    
    if not valid_loop_indices:
        return 0
    
    # Apply transform
    for loop_idx in valid_loop_indices:
        uv = uv_layer.data[loop_idx].uv
        uv_layer.data[loop_idx].uv = (
            uv[0] * scale[0] + offset[0],
            uv[1] * scale[1] + offset[1],
        )
    
    return len(valid_loop_indices)


def transform_material_uvs(
    mesh: bpy.types.Object,
    material_name: str,
    uv_layer_name: str,
    scale: Tuple[float, float],
    offset: Tuple[float, float],
) -> int:
    """
    Transform UVs for faces using a specific material.
    
    Args:
        mesh: The mesh object
        material_name: Material to filter by
        uv_layer_name: UV layer to transform
        scale: (scale_u, scale_v)
        offset: (offset_u, offset_v)
        
    Returns:
        Number of faces transformed
    """
    if mesh.type != "MESH":
        return 0
    
    # Find material index
    material = bpy.data.materials.get(material_name)
    if not material:
        return 0
    
    mat_index = -1
    for idx, mat_slot in enumerate(mesh.material_slots):
        if mat_slot.material == material:
            mat_index = idx
            break
    
    if mat_index < 0:
        return 0
    
    # Get face indices for this material
    face_indices = [
        poly.index for poly in mesh.data.polygons
        if poly.material_index == mat_index
    ]
    
    if not face_indices:
        return 0
    
    transform_uv_layer(mesh, uv_layer_name, scale, offset, face_indices)
    return len(face_indices)


def normalize_uv_bounds(
    mesh: bpy.types.Object,
    uv_layer_name: str,
    face_indices: Optional[List[int]] = None,
    target_min: Tuple[float, float] = (0.0, 0.0),
    target_max: Tuple[float, float] = (1.0, 1.0),
) -> bool:
    """
    Normalize UVs to fit within target bounds.
    
    Useful for fitting an island or material's UVs to a tile.
    
    Args:
        mesh: The mesh object
        uv_layer_name: UV layer to transform
        face_indices: Optional list of face indices.
                     If None, uses all faces.
        target_min: Target minimum bounds
        target_max: Target maximum bounds
        
    Returns:
        True if successful
    """
    if mesh.type != "MESH":
        return False
    
    if uv_layer_name not in mesh.data.uv_layers:
        return False
    
    uv_layer = mesh.data.uv_layers[uv_layer_name]
    
    # Build loop indices
    if face_indices is not None:
        loop_indices = []
        for poly in mesh.data.polygons:
            if poly.index in face_indices:
                loop_indices.extend(poly.loop_indices)
    else:
        loop_indices = list(range(len(uv_layer.data)))
    
    if not loop_indices:
        return False
    
    # Find current bounds
    u_coords = [uv_layer.data[i].uv[0] for i in loop_indices]
    v_coords = [uv_layer.data[i].uv[1] for i in loop_indices]
    
    current_min = (min(u_coords), min(v_coords))
    current_max = (max(u_coords), max(v_coords))
    
    current_size = (
        current_max[0] - current_min[0],
        current_max[1] - current_min[1],
    )
    
    if current_size[0] <= 0 or current_size[1] <= 0:
        return False
    
    target_size = (
        target_max[0] - target_min[0],
        target_max[1] - target_min[1],
    )
    
    # Calculate scale and offset
    scale = (
        target_size[0] / current_size[0],
        target_size[1] / current_size[1],
    )
    
    # Apply: first translate to origin, then scale, then translate to target
    for loop_idx in loop_indices:
        uv = uv_layer.data[loop_idx].uv
        normalized = (
            (uv[0] - current_min[0]) / current_size[0],
            (uv[1] - current_min[1]) / current_size[1],
        )
        uv_layer.data[loop_idx].uv = (
            normalized[0] * target_size[0] + target_min[0],
            normalized[1] * target_size[1] + target_min[1],
        )
    
    return True


def get_uv_bounds(
    mesh: bpy.types.Object,
    uv_layer_name: str,
    face_indices: Optional[List[int]] = None,
) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """
    Get the UV bounds for faces.
    
    Args:
        mesh: The mesh object
        uv_layer_name: UV layer to analyze
        face_indices: Optional list of face indices.
                     If None, uses all faces.
        
    Returns:
        ((u_min, v_min), (u_max, v_max)) or None if invalid
    """
    if mesh.type != "MESH":
        return None
    
    if uv_layer_name not in mesh.data.uv_layers:
        return None
    
    uv_layer = mesh.data.uv_layers[uv_layer_name]
    
    # Build loop indices
    if face_indices is not None:
        loop_indices = []
        for poly in mesh.data.polygons:
            if poly.index in face_indices:
                loop_indices.extend(poly.loop_indices)
    else:
        loop_indices = list(range(len(uv_layer.data)))
    
    if not loop_indices:
        return None
    
    u_coords = [uv_layer.data[i].uv[0] for i in loop_indices]
    v_coords = [uv_layer.data[i].uv[1] for i in loop_indices]
    
    return ((min(u_coords), min(v_coords)), (max(u_coords), max(v_coords)))


def get_material_uv_bounds(
    mesh: bpy.types.Object,
    material_name: str,
    uv_layer_name: str = "UVMap",
) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """
    Get UV bounds for a specific material.
    
    Args:
        mesh: The mesh object
        material_name: Material to filter by
        uv_layer_name: UV layer to analyze
        
    Returns:
        ((u_min, v_min), (u_max, v_max)) or None if invalid
    """
    if mesh.type != "MESH":
        return None
    
    # Find material index
    material = bpy.data.materials.get(material_name)
    if not material:
        return None
    
    mat_index = -1
    for idx, mat_slot in enumerate(mesh.material_slots):
        if mat_slot.material == material:
            mat_index = idx
            break
    
    if mat_index < 0:
        return None
    
    face_indices = [
        poly.index for poly in mesh.data.polygons
        if poly.material_index == mat_index
    ]
    
    return get_uv_bounds(mesh, uv_layer_name, face_indices)


def calculate_uv_area(
    mesh: bpy.types.Object,
    uv_layer_name: str,
    face_indices: Optional[List[int]] = None,
) -> float:
    """
    Calculate the total UV area for faces.
    
    Args:
        mesh: The mesh object
        uv_layer_name: UV layer to analyze
        face_indices: Optional list of face indices.
                     If None, uses all faces.
        
    Returns:
        Total UV area (using shoelace formula)
    """
    if mesh.type != "MESH":
        return 0.0
    
    if uv_layer_name not in mesh.data.uv_layers:
        return 0.0
    
    uv_layer = mesh.data.uv_layers[uv_layer_name]
    
    total_area = 0.0
    
    for poly in mesh.data.polygons:
        if face_indices is not None and poly.index not in face_indices:
            continue
        
        # Get UV coordinates for this face
        uvs = [uv_layer.data[loop_idx].uv for loop_idx in poly.loop_indices]
        
        # Shoelace formula
        n = len(uvs)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += uvs[i][0] * uvs[j][1]
            area -= uvs[j][0] * uvs[i][1]
        
        total_area += abs(area) / 2.0
    
    return total_area


def calculate_texel_density(
    mesh: bpy.types.Object,
    uv_layer_name: str,
    texture_resolution: int,
    face_indices: Optional[List[int]] = None,
) -> float:
    """
    Calculate texel density (pixels per world unit).
    
    Args:
        mesh: The mesh object
        uv_layer_name: UV layer to analyze
        texture_resolution: Texture resolution in pixels
        face_indices: Optional list of face indices.
                     If None, uses all faces.
        
    Returns:
        Texel density (pixels per world unit squared)
    """
    if mesh.type != "MESH":
        return 0.0
    
    uv_area = calculate_uv_area(mesh, uv_layer_name, face_indices)
    if uv_area <= 0:
        return 0.0
    
    # Calculate world area
    world_area = 0.0
    for poly in mesh.data.polygons:
        if face_indices is not None and poly.index not in face_indices:
            continue
        world_area += poly.area
    
    if world_area <= 0:
        return 0.0
    
    # Texel density = (UV area * texture pixels) / world area
    pixel_area = uv_area * (texture_resolution ** 2)
    density = pixel_area / world_area
    
    return density
