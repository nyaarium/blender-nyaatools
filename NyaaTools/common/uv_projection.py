"""
UV Projection utilities for shape key transfer across topology changes.

This module provides:
- UV validation (collapsed faces, flipped winding)
- NumPy-accelerated UV projection for fast shape key transfer
- Barycentric interpolation for delta/weight transfer
"""

import bmesh
import numpy as np
from mathutils import Vector


# Relative tolerance for degenerate triangle detection
# Instead of fixed EPSILON, we compare denom against the triangle's scale
# to detect shape degeneracy (slivers/collapsed) not size degeneracy
RELATIVE_DEGEN_TOLERANCE = 1e-10

# Absolute floor to avoid division by zero on truly collapsed triangles
EPSILON_FLOOR = 1e-30

# Tolerance for point-in-triangle tests (handles float precision in UV coords)
POINT_IN_TRI_TOLERANCE = 1e-5


def validate_uvs(mesh_obj, uv_layer_index):
    """
    Validate UV map is usable for projection.
    If faces fail validation, selects them in edit mode.

    Args:
        mesh_obj: Blender mesh object
        uv_layer_index: Index of UV layer to validate

    Returns:
        True if validation passes

    Raises:
        Exception with descriptive error message
    """
    import bpy

    mesh_data = mesh_obj.data

    if len(mesh_data.uv_layers) == 0:
        raise Exception("Mesh has no UV map. Please UV unwrap the mesh first.")

    if uv_layer_index >= len(mesh_data.uv_layers):
        raise Exception(f"UV map index {uv_layer_index} does not exist.")

    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.faces.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.verify()

    collapsed_faces = []

    try:
        for face in bm.faces:
            uv_area = compute_signed_uv_area(face, uv_layer)
            if uv_area == 0.0:
                collapsed_faces.append(face.index)

        if collapsed_faces:
            bm.to_mesh(mesh_data)
            bm.free()

            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="DESELECT")
            bpy.ops.object.mode_set(mode="OBJECT")

            for face_idx in collapsed_faces:
                mesh_data.polygons[face_idx].select = True

            bpy.ops.object.mode_set(mode="EDIT")

            raise Exception(
                f"Found {len(collapsed_faces)} face(s) with zero UV area (collapsed). "
                f"The problematic faces have been selected in edit mode. "
                f"Fix UVs before applying modifier."
            )
    finally:
        if bm.is_valid:
            bm.free()

    return True


def compute_signed_uv_area(face, uv_layer):
    """Compute signed UV area of a face using shoelace formula."""
    uvs = [loop[uv_layer].uv for loop in face.loops]
    n = len(uvs)

    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += uvs[i].x * uvs[j].y
        area -= uvs[j].x * uvs[i].y

    return area / 2.0


# =============================================================================
# NumPy-Accelerated UV Projection
# =============================================================================


def extract_triangles_numpy(mesh_obj, uv_layer_index):
    """
    Extract UV triangles from mesh into NumPy arrays.

    Returns:
        tri_uvs: (N_triangles, 3, 2) - UV coords for each triangle vertex
        tri_verts: (N_triangles, 3) - vertex indices for each triangle
    """
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv[uv_layer_index]

    triangles_uv = []
    triangles_vert = []

    try:
        for face in bm.faces:
            loops = list(face.loops)
            uvs = [(loop[uv_layer].uv.x, loop[uv_layer].uv.y) for loop in loops]
            verts = [loop.vert.index for loop in loops]

            # Fan triangulation
            for i in range(1, len(loops) - 1):
                triangles_uv.append([uvs[0], uvs[i], uvs[i + 1]])
                triangles_vert.append([verts[0], verts[i], verts[i + 1]])
    finally:
        bm.free()

    tri_uvs = np.array(triangles_uv, dtype=np.float64)  # (N, 3, 2)
    tri_verts = np.array(triangles_vert, dtype=np.int32)  # (N, 3)

    return tri_uvs, tri_verts


def extract_verts_3d_numpy(mesh_obj):
    """
    Extract 3D vertex positions from mesh into NumPy array.

    Returns:
        verts_3d: (N_vertices, 3) - 3D positions
    """
    mesh_data = mesh_obj.data
    n_verts = len(mesh_data.vertices)
    verts_3d = np.zeros((n_verts, 3), dtype=np.float64)

    for i, v in enumerate(mesh_data.vertices):
        verts_3d[i] = [v.co.x, v.co.y, v.co.z]

    return verts_3d


def extract_final_uvs_numpy(mesh_obj, uv_layer_index):
    """
    Extract UV coordinates for each vertex in the final mesh.
    For seam vertices with multiple UVs, picks the first one found.

    Returns:
        uvs: (N_vertices, 2) - UV coords per vertex
    """
    mesh_data = mesh_obj.data
    uv_layer = mesh_data.uv_layers[uv_layer_index]
    n_verts = len(mesh_data.vertices)

    # Initialize with NaN to detect vertices without UVs
    uvs = np.full((n_verts, 2), np.nan, dtype=np.float64)

    for poly in mesh_data.polygons:
        for loop_idx in poly.loop_indices:
            vert_idx = mesh_data.loops[loop_idx].vertex_index
            if np.isnan(uvs[vert_idx, 0]):
                uv = uv_layer.data[loop_idx].uv
                uvs[vert_idx] = [uv.x, uv.y]

    return uvs


def barycentric_batch(points, triangles, final_verts_3d=None, tri_centroids_3d=None):
    """
    Compute barycentric coordinates for points against triangles.
    Uses chunked processing to manage memory.

    When a point lands on multiple triangles (overlapping UVs), uses 3D distance
    to triangle centroids as a tie-breaker if 3D data is provided.

    Args:
        points: (N, 2) query points (UV coordinates)
        triangles: (M, 3, 2) triangle vertices (UV coordinates)
        final_verts_3d: (N, 3) 3D positions of query points (optional, for tie-breaking)
        tri_centroids_3d: (M, 3) 3D centroids of triangles (optional, for tie-breaking)

    Returns:
        bary: (N, 3) barycentric coordinates (for best matching triangle)
        tri_idx: (N,) index of containing triangle (-1 if none)
    """
    use_3d_tiebreaker = final_verts_3d is not None and tri_centroids_3d is not None

    N = points.shape[0]
    M = triangles.shape[0]

    result_bary = np.zeros((N, 3), dtype=np.float64)
    result_tri = np.full(N, -1, dtype=np.int32)

    # Process in chunks to avoid memory explosion
    # Each chunk: (chunk_size, M, 3) bary array = chunk_size * M * 3 * 8 bytes
    # For M=7500, chunk=500: ~90MB per chunk
    chunk_size = 500

    for start in range(0, N, chunk_size):
        end = min(start + chunk_size, N)
        chunk_points = points[start:end]  # (C, 2)
        C = chunk_points.shape[0]

        # Broadcast: points (C, 1, 2), triangles (1, M, 3, 2)
        P = chunk_points[:, np.newaxis, :]  # (C, 1, 2)
        A = triangles[np.newaxis, :, 0, :]  # (1, M, 2)
        B = triangles[np.newaxis, :, 1, :]  # (1, M, 2)
        C_tri = triangles[np.newaxis, :, 2, :]  # (1, M, 2)

        # Vectors for barycentric computation
        v0 = C_tri - A  # (1, M, 2)
        v1 = B - A  # (1, M, 2)
        v2 = P - A  # (C, M, 2)

        # Dot products
        dot00 = np.sum(v0 * v0, axis=-1)  # (1, M)
        dot01 = np.sum(v0 * v1, axis=-1)  # (1, M)
        dot02 = np.sum(v0 * v2, axis=-1)  # (C, M)
        dot11 = np.sum(v1 * v1, axis=-1)  # (1, M)
        dot12 = np.sum(v1 * v2, axis=-1)  # (C, M)

        # Denominator with relative tolerance
        denom = dot00 * dot11 - dot01 * dot01  # (1, M)
        # Scale reference: product of squared edge lengths
        scale = dot00 * dot11  # (1, M)
        # Relative threshold: detect shape degeneracy, not size
        threshold = np.maximum(scale * RELATIVE_DEGEN_TOLERANCE, EPSILON_FLOOR)
        valid = np.abs(denom) > threshold

        # Safe division
        denom_safe = np.where(valid, denom, 1.0)
        inv_denom = 1.0 / denom_safe

        u = (dot11 * dot02 - dot01 * dot12) * inv_denom  # (C, M)
        v = (dot00 * dot12 - dot01 * dot02) * inv_denom  # (C, M)
        w = 1.0 - u - v

        # Check if inside triangle (with tolerance)
        tol = POINT_IN_TRI_TOLERANCE
        inside = (
            (w >= -tol) & (v >= -tol) & (u >= -tol) & np.broadcast_to(valid, (C, M))
        )  # (C, M)

        # For each point, find best matching triangle
        for i in range(C):
            matches = np.where(inside[i])[0]
            if len(matches) > 0:
                if len(matches) == 1 or not use_3d_tiebreaker:
                    tri = matches[0]
                else:
                    final_idx = start + i
                    final_pos = final_verts_3d[final_idx]  # (3,)
                    match_centroids = tri_centroids_3d[matches]  # (K, 3)
                    dists_3d = np.sum((match_centroids - final_pos) ** 2, axis=1)
                    tri = matches[np.argmin(dists_3d)]

                result_tri[start + i] = tri
                result_bary[start + i] = [w[i, tri], v[i, tri], u[i, tri]]

    return result_bary, result_tri


def find_nearest_triangles_numpy(points, triangles, missing_mask):
    """
    For points that didn't find a containing triangle, find the nearest one.
    Uses vectorized distance computation.

    Args:
        points: (N, 2) all query points
        triangles: (M, 3, 2) triangle vertices
        missing_mask: (N,) boolean mask of points needing nearest search

    Returns:
        bary: (N, 3) updated barycentric coords
        tri_idx: (N,) updated triangle indices
    """
    missing_indices = np.where(missing_mask)[0]
    if len(missing_indices) == 0:
        return np.zeros((len(points), 3)), np.full(len(points), -1, dtype=np.int32)

    N_missing = len(missing_indices)
    M = triangles.shape[0]

    result_bary = np.zeros((len(points), 3), dtype=np.float64)
    result_tri = np.full(len(points), -1, dtype=np.int32)

    # For nearest search, compute distance to triangle centroids first
    # Then refine with actual closest point computation
    centroids = triangles.mean(axis=1)  # (M, 2)

    # Process missing points in chunks
    chunk_size = 200

    for chunk_start in range(0, N_missing, chunk_size):
        chunk_end = min(chunk_start + chunk_size, N_missing)
        chunk_indices = missing_indices[chunk_start:chunk_end]
        chunk_points = points[chunk_indices]  # (C, 2)
        C = len(chunk_points)

        # Distance to all centroids: (C, M)
        diffs = chunk_points[:, np.newaxis, :] - centroids[np.newaxis, :, :]
        centroid_dists = np.sum(diffs * diffs, axis=-1)

        # For each point, check top-K nearest centroids
        K = min(50, M)
        for i in range(C):
            nearest_tris = np.argpartition(centroid_dists[i], K)[:K]
            pt = chunk_points[i]

            best_tri = -1
            best_dist = float("inf")
            best_closest = None

            for tri_idx in nearest_tris:
                tri = triangles[tri_idx]
                closest = closest_point_on_triangle_numpy(pt, tri)
                dist = np.sum((closest - pt) ** 2)
                if dist < best_dist:
                    best_dist = dist
                    best_tri = tri_idx
                    best_closest = closest

            if best_tri >= 0:
                # Compute barycentric at closest point
                tri = triangles[best_tri]
                bary = compute_barycentric_single(best_closest, tri)
                result_tri[chunk_indices[i]] = best_tri
                result_bary[chunk_indices[i]] = bary

    return result_bary, result_tri


def closest_point_on_triangle_numpy(point, triangle):
    """Find closest point on triangle to a 2D point."""
    A, B, C = triangle[0], triangle[1], triangle[2]

    # Check if inside
    bary = compute_barycentric_single(point, triangle)
    if (
        bary[0] >= -POINT_IN_TRI_TOLERANCE
        and bary[1] >= -POINT_IN_TRI_TOLERANCE
        and bary[2] >= -POINT_IN_TRI_TOLERANCE
    ):
        return point.copy()

    # Find closest on each edge
    candidates = [
        closest_point_on_segment_numpy(point, A, B),
        closest_point_on_segment_numpy(point, B, C),
        closest_point_on_segment_numpy(point, C, A),
    ]

    dists = [np.sum((c - point) ** 2) for c in candidates]
    return candidates[np.argmin(dists)]


def closest_point_on_segment_numpy(point, seg_a, seg_b):
    """Find closest point on segment."""
    ab = seg_b - seg_a
    ab_len_sq = np.dot(ab, ab)

    if ab_len_sq < EPSILON_FLOOR:
        return seg_a.copy()

    t = np.dot(point - seg_a, ab) / ab_len_sq
    t = max(0.0, min(1.0, t))

    return seg_a + ab * t


def compute_barycentric_single(point, triangle):
    """Compute barycentric coordinates for a single point/triangle."""
    A, B, C = triangle[0], triangle[1], triangle[2]

    v0 = C - A
    v1 = B - A
    v2 = point - A

    dot00 = np.dot(v0, v0)
    dot01 = np.dot(v0, v1)
    dot02 = np.dot(v0, v2)
    dot11 = np.dot(v1, v1)
    dot12 = np.dot(v1, v2)

    denom = dot00 * dot11 - dot01 * dot01
    # Relative threshold based on triangle scale
    scale = dot00 * dot11
    threshold = max(scale * RELATIVE_DEGEN_TOLERANCE, EPSILON_FLOOR)
    if abs(denom) < threshold:
        return np.array([1.0, 0.0, 0.0])

    inv_denom = 1.0 / denom
    u = (dot11 * dot02 - dot01 * dot12) * inv_denom
    v = (dot00 * dot12 - dot01 * dot02) * inv_denom
    w = 1.0 - u - v

    return np.array([w, v, u])


def project_uvs_numpy(
    original_mesh,
    final_mesh,
    uv_layer_index,
    shape_deltas,
    vertex_weights,
):
    """
    Project shape key deltas and vertex weights from original to final mesh
    using NumPy-accelerated UV projection.

    Sampling pipeline (orig -> final for each final vertex):
    1. Extract triangles from ORIGINAL: each face triangulated (fan), each tri has
       (tri_uvs, tri_verts) = UV coords and original vertex indices.
    2. Extract per-vertex UVs from FINAL: one (u,v) per final vertex (first loop wins at seams).
    3. For each final vertex, take its UV as a 2D point. Find which original triangle
       contains that point (point-in-triangle test with tolerance). If multiple tris
       contain it (overlapping UVs), use 3D tie-breaker: choose the tri whose 3D
       centroid is closest to this final vertex's 3D position.
    4. Compute barycentric coords (w,v,u) of the point in that triangle. Stored as
       [w, v, u] so bary[0]=weight for tri_verts[0], bary[1]=for tri_verts[1], bary[2]=for tri_verts[2].
    5. If no triangle contains the point, use nearest-triangle fallback: project point
       onto closest triangle, get barycentric at that projected point.
    6. Interpolate: result_delta = d0*bary[0] + d1*bary[1] + d2*bary[2] where d0,d1,d2
       are the shape key deltas at the three original vertices tri_verts[0,1,2].

    Args:
        original_mesh: Blender mesh object (source with shape keys)
        final_mesh: Blender mesh object (target with new topology)
        uv_layer_index: UV layer to use for projection
        shape_deltas: dict {name: [Vector3 per vertex]} from original
        vertex_weights: dict {name: [float per vertex]} from original

    Returns:
        (projected_deltas, projected_weights) for final mesh
    """
    # Extract data to NumPy
    tri_uvs, tri_verts = extract_triangles_numpy(original_mesh, uv_layer_index)
    final_uvs = extract_final_uvs_numpy(final_mesh, uv_layer_index)
    n_final = len(final_uvs)
    n_orig = len(original_mesh.data.vertices)

    # Extract 3D vertex positions for tie-breaking overlapping UVs
    orig_verts_3d = extract_verts_3d_numpy(original_mesh)
    final_verts_3d = extract_verts_3d_numpy(final_mesh)

    # Compute triangle 3D centroids from original mesh vertex positions
    # tri_verts: (M, 3) vertex indices -> use to gather 3D positions
    tri_positions_3d = orig_verts_3d[tri_verts]  # (M, 3, 3)
    tri_centroids_3d = tri_positions_3d.mean(axis=1)  # (M, 3)

    # Convert shape deltas to NumPy: (N_keys, N_orig, 3)
    delta_names = list(shape_deltas.keys())
    if delta_names:
        deltas_np = np.array(
            [[list(d) for d in shape_deltas[name]] for name in delta_names],
            dtype=np.float64,
        )
    else:
        deltas_np = np.zeros((0, n_orig, 3), dtype=np.float64)

    # Convert vertex weights to NumPy: (N_groups, N_orig)
    weight_names = list(vertex_weights.keys())
    if weight_names:
        weights_np = np.array(
            [vertex_weights[name] for name in weight_names], dtype=np.float64
        )
    else:
        weights_np = np.zeros((0, n_orig), dtype=np.float64)

    # Find containing triangles (vectorized)
    # Pass 3D data for tie-breaking when UV point lands on multiple triangles
    bary, tri_idx = barycentric_batch(
        final_uvs, tri_uvs, final_verts_3d, tri_centroids_3d
    )

    # Count misses and handle with nearest search
    missing_mask = tri_idx < 0
    n_missing = np.sum(missing_mask)

    # Handle missing with nearest search
    if n_missing > 0:
        bary_nearest, tri_nearest = find_nearest_triangles_numpy(
            final_uvs, tri_uvs, missing_mask
        )
        # Merge results
        bary[missing_mask] = bary_nearest[missing_mask]
        tri_idx[missing_mask] = tri_nearest[missing_mask]

    # Get triangle vertex indices for each final vertex
    # tri_idx: (N_final,), tri_verts: (N_tri, 3)
    valid_mask = tri_idx >= 0
    valid_indices = np.where(valid_mask)[0]

    # For valid vertices, get the 3 original vertex indices
    matched_tri_verts = tri_verts[tri_idx[valid_mask]]  # (N_valid, 3)

    # Interpolate deltas
    projected_deltas = {}
    for i, name in enumerate(delta_names):
        result = np.zeros((n_final, 3), dtype=np.float64)
        if len(valid_indices) > 0:
            # Get deltas for the 3 vertices of each matched triangle
            d0 = deltas_np[i, matched_tri_verts[:, 0]]  # (N_valid, 3)
            d1 = deltas_np[i, matched_tri_verts[:, 1]]
            d2 = deltas_np[i, matched_tri_verts[:, 2]]

            # Barycentric interpolation
            b = bary[valid_mask]  # (N_valid, 3)
            interpolated = d0 * b[:, 0:1] + d1 * b[:, 1:2] + d2 * b[:, 2:3]
            result[valid_mask] = interpolated

        projected_deltas[name] = [Vector(result[j]) for j in range(n_final)]

    # Interpolate weights
    projected_weights = {}
    for i, name in enumerate(weight_names):
        result = np.zeros(n_final, dtype=np.float64)
        if len(valid_indices) > 0:
            w0 = weights_np[i, matched_tri_verts[:, 0]]
            w1 = weights_np[i, matched_tri_verts[:, 1]]
            w2 = weights_np[i, matched_tri_verts[:, 2]]

            b = bary[valid_mask]
            interpolated = w0 * b[:, 0] + w1 * b[:, 1] + w2 * b[:, 2]
            result[valid_mask] = interpolated

        projected_weights[name] = list(result)

    return projected_deltas, projected_weights


def project_positions_via_uv(
    source_mesh,
    target_mesh,
    uv_layer_index,
):
    """
    Project 3D positions from source mesh to target mesh via UV coordinates.

    For each vertex in target_mesh, finds its UV in source_mesh's triangles
    and interpolates the 3D position using barycentric coordinates.

    This is used for the per-shape-key algorithm: apply modifier to each SK state,
    then project positions from each result back to the Basis result to compute deltas.

    Args:
        source_mesh: Blender mesh object (has 3D positions to sample from)
        target_mesh: Blender mesh object (has UVs to look up)
        uv_layer_index: UV layer to use for projection

    Returns:
        projected_positions: list of Vector3 (one per target vertex)
        - For each target vertex, the interpolated 3D position from source
    """
    # Extract data to NumPy
    tri_uvs, tri_verts = extract_triangles_numpy(source_mesh, uv_layer_index)
    target_uvs = extract_final_uvs_numpy(target_mesh, uv_layer_index)
    n_target = len(target_uvs)

    # Extract 3D vertex positions from source mesh
    source_verts_3d = extract_verts_3d_numpy(source_mesh)
    target_verts_3d = extract_verts_3d_numpy(target_mesh)

    # Compute triangle 3D centroids for tie-breaking overlapping UVs
    tri_positions_3d = source_verts_3d[tri_verts]  # (M, 3, 3)
    tri_centroids_3d = tri_positions_3d.mean(axis=1)  # (M, 3)

    # Find containing triangles (vectorized)
    bary, tri_idx = barycentric_batch(
        target_uvs, tri_uvs, target_verts_3d, tri_centroids_3d
    )

    # Handle missing with nearest search
    missing_mask = tri_idx < 0
    n_missing = np.sum(missing_mask)

    if n_missing > 0:
        bary_nearest, tri_nearest = find_nearest_triangles_numpy(
            target_uvs, tri_uvs, missing_mask
        )
        bary[missing_mask] = bary_nearest[missing_mask]
        tri_idx[missing_mask] = tri_nearest[missing_mask]

    # Get triangle vertex indices for each target vertex
    valid_mask = tri_idx >= 0
    valid_indices = np.where(valid_mask)[0]

    # Initialize result with target positions (fallback for invalid)
    result_positions = target_verts_3d.copy()

    if len(valid_indices) > 0:
        # For valid vertices, get the 3 source vertex indices
        matched_tri_verts = tri_verts[tri_idx[valid_mask]]  # (N_valid, 3)

        # Get 3D positions for the 3 vertices of each matched triangle
        p0 = source_verts_3d[matched_tri_verts[:, 0]]  # (N_valid, 3)
        p1 = source_verts_3d[matched_tri_verts[:, 1]]
        p2 = source_verts_3d[matched_tri_verts[:, 2]]

        # Barycentric interpolation of positions
        b = bary[valid_mask]  # (N_valid, 3)
        interpolated = p0 * b[:, 0:1] + p1 * b[:, 1:2] + p2 * b[:, 2:3]
        result_positions[valid_mask] = interpolated

    # Convert to list of Vectors
    return [Vector(result_positions[j]) for j in range(n_target)]


# =============================================================================
# Legacy functions (kept for compatibility)
# =============================================================================


def barycentric_2d(point, triangle):
    """Compute barycentric coordinates for point P in triangle ABC."""
    a, b, c = triangle
    p = point

    v0 = c - a
    v1 = b - a
    v2 = p - a

    dot00 = v0.dot(v0)
    dot01 = v0.dot(v1)
    dot02 = v0.dot(v2)
    dot11 = v1.dot(v1)
    dot12 = v1.dot(v2)

    denom = dot00 * dot11 - dot01 * dot01
    # Relative threshold based on triangle scale
    scale = dot00 * dot11
    threshold = max(scale * RELATIVE_DEGEN_TOLERANCE, EPSILON_FLOOR)
    if abs(denom) < threshold:
        return None

    inv_denom = 1.0 / denom
    u = (dot11 * dot02 - dot01 * dot12) * inv_denom
    v = (dot00 * dot12 - dot01 * dot02) * inv_denom
    w = 1.0 - u - v

    return Vector((w, v, u))


def extract_shape_key_deltas(mesh_obj):
    """Extract shape key deltas relative to Basis."""
    if not mesh_obj.data.shape_keys:
        return {}

    key_blocks = mesh_obj.data.shape_keys.key_blocks
    basis = key_blocks.get("Basis") or key_blocks[0]
    basis_coords = [v.co.copy() for v in basis.data]

    deltas = {}
    for key in key_blocks:
        if key == basis:
            continue

        key_deltas = [
            key.data[i].co - basis_coords[i] for i in range(len(basis_coords))
        ]
        deltas[key.name] = key_deltas

    return deltas


def extract_vertex_group_weights(mesh_obj):
    """Extract vertex group weights per vertex."""
    weights = {}

    for vgroup in mesh_obj.vertex_groups:
        group_weights = []
        for v in mesh_obj.data.vertices:
            try:
                w = vgroup.weight(v.index)
            except RuntimeError:
                w = 0.0
            group_weights.append(w)
        weights[vgroup.name] = group_weights

    return weights


def extract_shape_key_metadata(mesh_obj):
    """Extract shape key metadata for later restoration."""
    if not mesh_obj.data.shape_keys:
        return []

    metadata = []
    for key in mesh_obj.data.shape_keys.key_blocks:
        metadata.append(
            {
                "name": key.name,
                "interpolation": key.interpolation,
                "mute": key.mute,
                "slider_min": key.slider_min,
                "slider_max": key.slider_max,
                "value": key.value,
                "vertex_group": key.vertex_group,
                "relative_key_name": (
                    key.relative_key.name if key.relative_key else None
                ),
            }
        )

    return metadata


def interpolate_delta(triangle, bary, deltas):
    """Interpolate a delta value using barycentric coordinates."""
    v0, v1, v2 = triangle["vert_indices"]
    d0 = deltas[v0]
    d1 = deltas[v1]
    d2 = deltas[v2]

    return d0 * bary.x + d1 * bary.y + d2 * bary.z


def interpolate_weight(triangle, bary, weights):
    """Interpolate a weight value using barycentric coordinates."""
    v0, v1, v2 = triangle["vert_indices"]
    w0 = weights[v0]
    w1 = weights[v1]
    w2 = weights[v2]

    return w0 * bary.x + w1 * bary.y + w2 * bary.z
