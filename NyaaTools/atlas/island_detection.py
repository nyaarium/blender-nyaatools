"""
UV island detection utilities.

Wraps Blender's built-in UV island detection for use in atlas operations.
"""

from __future__ import annotations
from typing import List, Dict, Set, Tuple, Optional, Any
import bpy
import bmesh


def detect_uv_islands(
    mesh: bpy.types.Object,
    uv_layer_name: str = "UVMap",
    material_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Detect UV islands in a mesh.
    
    Uses connected component analysis based on UV edge connectivity.
    
    Args:
        mesh: The mesh object
        uv_layer_name: UV layer to analyze
        material_filter: Optional material name to filter by
        
    Returns:
        List of island dicts containing:
        - face_indices: List of polygon indices
        - loop_indices: List of loop indices
        - bounds_min: (u_min, v_min)
        - bounds_max: (u_max, v_max)
        - uv_area: Total UV area
        - world_area: Total world surface area
    """
    if mesh.type != "MESH":
        return []
    
    # Get material index filter
    mat_index = None
    if material_filter:
        material = bpy.data.materials.get(material_filter)
        if material:
            for idx, mat_slot in enumerate(mesh.material_slots):
                if mat_slot.material == material:
                    mat_index = idx
                    break
    
    # Use BMesh for island detection
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    bm.faces.ensure_lookup_table()
    
    uv_layer = bm.loops.layers.uv.get(uv_layer_name)
    if not uv_layer:
        bm.free()
        return []
    
    # Filter faces
    if mat_index is not None:
        faces = [f for f in bm.faces if f.material_index == mat_index]
    else:
        faces = list(bm.faces)
    
    if not faces:
        bm.free()
        return []
    
    # Detect islands
    islands = _detect_islands_bmesh(bm, faces, uv_layer)
    
    bm.free()
    return islands


def _detect_islands_bmesh(
    bm: bmesh.types.BMesh,
    faces: List[bmesh.types.BMFace],
    uv_layer: bmesh.types.BMLoopUV,
) -> List[Dict[str, Any]]:
    """
    Detect UV islands from faces using connected component analysis.
    """
    if not faces:
        return []
    
    face_set = set(faces)
    face_to_idx = {f: i for i, f in enumerate(faces)}
    
    # Union-Find
    parent = list(range(len(faces)))
    
    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    
    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py
    
    # UV coordinate tolerance
    UV_EPSILON = 1e-5
    
    # Build UV edge map
    uv_edge_map: Dict[Tuple, List[int]] = {}
    
    for face in faces:
        face_idx = face_to_idx[face]
        loops = list(face.loops)
        
        for i, loop in enumerate(loops):
            next_loop = loops[(i + 1) % len(loops)]
            
            uv1 = loop[uv_layer].uv.copy()
            uv2 = next_loop[uv_layer].uv.copy()
            
            # Quantize for hashing
            key1 = (round(uv1.x / UV_EPSILON), round(uv1.y / UV_EPSILON))
            key2 = (round(uv2.x / UV_EPSILON), round(uv2.y / UV_EPSILON))
            
            edge_key = tuple(sorted([key1, key2]))
            
            if edge_key not in uv_edge_map:
                uv_edge_map[edge_key] = []
            uv_edge_map[edge_key].append(face_idx)
    
    # Union faces sharing UV edges
    for edge_key, face_indices in uv_edge_map.items():
        for i in range(1, len(face_indices)):
            union(face_indices[0], face_indices[i])
    
    # Group by island
    island_groups: Dict[int, List[bmesh.types.BMFace]] = {}
    for face in faces:
        face_idx = face_to_idx[face]
        root = find(face_idx)
        if root not in island_groups:
            island_groups[root] = []
        island_groups[root].append(face)
    
    # Build island data
    islands = []
    for root, island_faces in island_groups.items():
        u_coords = []
        v_coords = []
        loop_indices = []
        face_indices = []
        uv_area = 0.0
        world_area = 0.0
        
        for face in island_faces:
            face_indices.append(face.index)
            world_area += face.calc_area()
            
            # UV area (shoelace)
            uvs = [loop[uv_layer].uv for loop in face.loops]
            n = len(uvs)
            face_uv_area = 0.0
            for i in range(n):
                j = (i + 1) % n
                face_uv_area += uvs[i].x * uvs[j].y
                face_uv_area -= uvs[j].x * uvs[i].y
            uv_area += abs(face_uv_area) / 2.0
            
            for loop in face.loops:
                uv = loop[uv_layer].uv
                u_coords.append(uv.x)
                v_coords.append(uv.y)
                loop_indices.append(loop.index)
        
        if u_coords:
            bounds_min = (min(u_coords), min(v_coords))
            bounds_max = (max(u_coords), max(v_coords))
        else:
            bounds_min = (0.0, 0.0)
            bounds_max = (1.0, 1.0)
        
        islands.append({
            "face_indices": face_indices,
            "loop_indices": loop_indices,
            "bounds_min": bounds_min,
            "bounds_max": bounds_max,
            "uv_area": uv_area,
            "world_area": world_area,
        })
    
    return islands


def get_island_count(
    mesh: bpy.types.Object,
    uv_layer_name: str = "UVMap",
    material_filter: Optional[str] = None,
) -> int:
    """
    Get the number of UV islands.
    
    Args:
        mesh: The mesh object
        uv_layer_name: UV layer to analyze
        material_filter: Optional material to filter by
        
    Returns:
        Number of islands
    """
    islands = detect_uv_islands(mesh, uv_layer_name, material_filter)
    return len(islands)


def get_island_bounds(
    mesh: bpy.types.Object,
    uv_layer_name: str = "UVMap",
    material_filter: Optional[str] = None,
) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """
    Get bounds for all UV islands.
    
    Args:
        mesh: The mesh object
        uv_layer_name: UV layer to analyze
        material_filter: Optional material to filter by
        
    Returns:
        List of ((u_min, v_min), (u_max, v_max)) bounds
    """
    islands = detect_uv_islands(mesh, uv_layer_name, material_filter)
    return [(i["bounds_min"], i["bounds_max"]) for i in islands]


def select_island_faces(
    mesh: bpy.types.Object,
    island_index: int,
    uv_layer_name: str = "UVMap",
    material_filter: Optional[str] = None,
) -> bool:
    """
    Select faces belonging to a specific island.
    
    Args:
        mesh: The mesh object
        island_index: Index of the island to select
        uv_layer_name: UV layer to use
        material_filter: Optional material to filter by
        
    Returns:
        True if successful
    """
    islands = detect_uv_islands(mesh, uv_layer_name, material_filter)
    
    if island_index < 0 or island_index >= len(islands):
        return False
    
    island = islands[island_index]
    face_indices = set(island["face_indices"])
    
    # Enter edit mode if needed
    was_object_mode = bpy.context.mode == "OBJECT"
    if was_object_mode:
        bpy.ops.object.mode_set(mode="EDIT")
    
    # Deselect all
    bpy.ops.mesh.select_all(action="DESELECT")
    
    # Switch to face select
    bpy.ops.mesh.select_mode(type="FACE")
    
    # Back to object mode to select faces
    bpy.ops.object.mode_set(mode="OBJECT")
    
    for poly in mesh.data.polygons:
        poly.select = poly.index in face_indices
    
    # Back to edit mode
    bpy.ops.object.mode_set(mode="EDIT")
    
    if was_object_mode:
        bpy.ops.object.mode_set(mode="OBJECT")
    
    return True
