"""
UV Auto-Fix utilities for shape key projection.

This module provides automatic UV fixing for the UV projection algorithm:
- Vortex fixer: handles collapsed (0 boundary) and distorted vortex islands via bootstrap + seam repair
- Resolves overlapping UV islands by shifting them apart

These fixes are applied to a temporary UV layer that is discarded after projection.
The original UV layout is never modified.
"""

import bmesh
from mathutils import Vector

from .fix_vortex_uvs import detect_and_fix_vortex_islands


# Margin between islands when resolving overlaps
OVERLAP_MARGIN = 0.01


def auto_fix_uvs_for_projection(context, mesh_obj, uv_layer_index):
    """
    Create a temporary fixed UV layer suitable for projection.

    Fixes:
    1. Collapsed and vortex islands - via vortex fixer (bootstrap for 0-boundary, seam repair for distortion)
    2. Overlapping islands - shifts them apart on U axis

    Args:
        context: Blender context
        mesh_obj: Blender mesh object
        uv_layer_index: Source UV layer index to copy and fix

    Returns:
        temp_uv_index: Index of the created temporary UV layer
        stats: Dict with fix statistics
    """
    mesh_data = mesh_obj.data

    # Remember active UV slot so we can restore it after (temp is appended, indices unchanged)
    saved_active_index = mesh_data.uv_layers.active_index

    # Create temp UV layer by duplicating the source
    source_uv = mesh_data.uv_layers[uv_layer_index]
    temp_uv = mesh_data.uv_layers.new(name="_TEMP_PROJECTION_UV")
    temp_uv_index = list(mesh_data.uv_layers).index(temp_uv)

    # Copy UV data from source to temp
    for i in range(len(mesh_data.loops)):
        temp_uv.data[i].uv = source_uv.data[i].uv.copy()

    # Vortex fixer: bootstraps closed/collapsed islands (0 boundary) and repairs vortex distortion
    # restore_seams=True removes any seams added during the fix process
    vortex_stats = detect_and_fix_vortex_islands(
        context, mesh_obj, temp_uv_index, restore_seams=True
    )

    # Resolve overlapping islands so each UV point lands in at most one triangle.
    # Safe here because we fix once on the source mesh, then duplicate – both copies inherit.
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv[temp_uv_index]
    islands = detect_uv_islands(bm, uv_layer)
    overlap_shifts = resolve_island_overlaps(islands, bm, uv_layer)
    bm.to_mesh(mesh_data)
    bm.free()

    # Restore the user's active UV layer selection
    mesh_data.uv_layers.active_index = saved_active_index

    return temp_uv_index, {
        "num_islands": vortex_stats["islands_checked"],
        "vortexes_found": vortex_stats["vortexes_found"],
        "vortexes_fixed": vortex_stats["vortexes_fixed"],
        "overlap_shifts": overlap_shifts,
    }


def create_temp_uv_layer(mesh_obj, uv_layer_index):
    """
    Create a temporary UV layer by copying the source (no fixing).

    Used for the final mesh where we want unmodified UVs.

    Args:
        mesh_obj: Blender mesh object
        uv_layer_index: Source UV layer index to copy

    Returns:
        temp_uv_index: Index of the created temporary UV layer
    """
    mesh_data = mesh_obj.data

    # Remember active UV slot so we can restore it after
    saved_active_index = mesh_data.uv_layers.active_index

    # Create temp UV layer by duplicating the source
    source_uv = mesh_data.uv_layers[uv_layer_index]
    temp_uv = mesh_data.uv_layers.new(name="_TEMP_PROJECTION_UV")
    temp_uv_index = list(mesh_data.uv_layers).index(temp_uv)

    # Copy UV data from source to temp
    for i in range(len(mesh_data.loops)):
        temp_uv.data[i].uv = source_uv.data[i].uv.copy()

    # Restore the user's active UV layer selection
    mesh_data.uv_layers.active_index = saved_active_index

    return temp_uv_index


def cleanup_temp_uv_layer(mesh_obj, temp_uv_index):
    """Remove the temporary UV layer after projection is complete."""
    mesh_data = mesh_obj.data
    if temp_uv_index < len(mesh_data.uv_layers):
        temp_layer = mesh_data.uv_layers[temp_uv_index]
        if temp_layer.name == "_TEMP_PROJECTION_UV":
            mesh_data.uv_layers.remove(temp_layer)


def detect_uv_islands(bm, uv_layer):
    """
    Detect UV islands using connected component analysis.

    Two faces are in the same island if they share an edge where
    the UV coordinates match at both endpoints.

    Args:
        bm: BMesh object
        uv_layer: BMesh UV layer

    Returns:
        List of islands, where each island is a set of face indices
    """
    visited = set()
    islands = []

    for face in bm.faces:
        if face.index in visited:
            continue

        # BFS to find connected component
        island = set()
        queue = [face]

        while queue:
            f = queue.pop()
            if f.index in visited:
                continue
            visited.add(f.index)
            island.add(f.index)

            # Find UV-adjacent faces
            for loop in f.loops:
                edge = loop.edge
                for linked_face in edge.link_faces:
                    if linked_face.index not in visited:
                        if uvs_match_at_edge(f, linked_face, edge, uv_layer):
                            queue.append(linked_face)

        islands.append(island)

    return islands


def uvs_match_at_edge(face1, face2, edge, uv_layer, tolerance=1e-6):
    """Check if two faces share matching UVs at a shared edge."""

    def get_edge_uvs(face, edge):
        """Get UV coords for the two verts of an edge within a face."""
        uvs = {}
        for loop in face.loops:
            if loop.vert in edge.verts:
                uvs[loop.vert.index] = loop[uv_layer].uv.copy()
        return uvs

    uvs1 = get_edge_uvs(face1, edge)
    uvs2 = get_edge_uvs(face2, edge)

    if len(uvs1) != 2 or len(uvs2) != 2:
        return False

    # Check if UVs match at each vertex
    for vert_idx in uvs1:
        if vert_idx not in uvs2:
            return False
        if (uvs1[vert_idx] - uvs2[vert_idx]).length > tolerance:
            return False

    return True


def get_island_bbox(island_faces, bm, uv_layer):
    """
    Get axis-aligned bounding box for an island.

    Returns:
        (min_u, min_v, max_u, max_v)
    """
    min_u, min_v = float("inf"), float("inf")
    max_u, max_v = float("-inf"), float("-inf")

    for face_idx in island_faces:
        face = bm.faces[face_idx]
        for loop in face.loops:
            uv = loop[uv_layer].uv
            min_u = min(min_u, uv.x)
            min_v = min(min_v, uv.y)
            max_u = max(max_u, uv.x)
            max_v = max(max_v, uv.y)

    return (min_u, min_v, max_u, max_v)


def bboxes_overlap(bbox1, bbox2):
    """Check if two bounding boxes overlap."""
    min_u1, min_v1, max_u1, max_v1 = bbox1
    min_u2, min_v2, max_u2, max_v2 = bbox2

    # Check for separation on either axis
    if max_u1 <= min_u2 or max_u2 <= min_u1:
        return False
    if max_v1 <= min_v2 or max_v2 <= min_v1:
        return False

    return True


def translate_island(island_faces, bm, uv_layer, offset):
    """Translate all UVs in an island by offset (u, v)."""
    # Track which UV coords we've already moved (shared verts at seams)
    moved = set()

    for face_idx in island_faces:
        face = bm.faces[face_idx]
        for loop in face.loops:
            # Create a unique key for this loop's UV
            key = (face_idx, loop.vert.index)
            if key not in moved:
                loop[uv_layer].uv.x += offset[0]
                loop[uv_layer].uv.y += offset[1]
                moved.add(key)


def resolve_island_overlaps(islands, bm, uv_layer):
    """
    Resolve overlapping islands by shifting them apart.

    Strategy: Sort islands by leftmost edge, then shift overlapping
    islands to the right until no overlap.

    Returns:
        Number of shift operations performed
    """
    if len(islands) <= 1:
        return 0

    # Compute initial bboxes
    bboxes = [get_island_bbox(island, bm, uv_layer) for island in islands]

    # Sort islands by min_u (leftmost first)
    sorted_indices = sorted(range(len(islands)), key=lambda i: bboxes[i][0])

    total_shifts = 0
    max_iterations = 1000  # Safety limit

    # Process each island
    for i in range(1, len(sorted_indices)):
        idx = sorted_indices[i]
        island = islands[idx]

        iteration = 0
        needs_shift = True

        while needs_shift and iteration < max_iterations:
            needs_shift = False
            current_bbox = get_island_bbox(island, bm, uv_layer)

            # Check against all prior islands
            for j in range(i):
                prior_idx = sorted_indices[j]
                prior_bbox = get_island_bbox(islands[prior_idx], bm, uv_layer)

                if bboxes_overlap(current_bbox, prior_bbox):
                    # Calculate shift needed to clear the overlap
                    shift_amount = prior_bbox[2] - current_bbox[0] + OVERLAP_MARGIN
                    translate_island(island, bm, uv_layer, (shift_amount, 0.0))
                    total_shifts += 1
                    needs_shift = True
                    break

            iteration += 1

    return total_shifts
