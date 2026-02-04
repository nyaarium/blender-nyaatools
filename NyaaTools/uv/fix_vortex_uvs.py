"""
UV Vortex Detection and Repair.

This module detects and fixes UV islands with severe distortion ("vortex" pattern)
where faces spiral inward, creating extreme texel density variation.

The algorithm:
1. Compute texel density (3D area / UV area) for each face
2. Detect vortex islands by high density variance
3. Iteratively add seams and re-unwrap until fixed
4. Restore original seam state when done
"""

import bpy
import bmesh
import numpy as np
from mathutils import Vector

# Threshold for vortex detection: max_density/min_density ratio
VORTEX_DENSITY_RATIO_THRESHOLD = 15.0

# Threshold for shape distortion: max coefficient of variation (CV)
# CV = std(edge_ratios) / mean(edge_ratios) for each face
# CV=0 means uniform scaling, CV>0.3 means heavily stretched
VORTEX_SHAPE_CV_THRESHOLD = 0.3

# Maximum iterations for vortex repair loop
MAX_VORTEX_ITERATIONS = 10

# Minimum UV area to avoid division by zero
MIN_UV_AREA = 1e-12


def compute_face_uv_area(face, uv_layer):
    """
    Compute UV area for a single face using shoelace formula.

    Args:
        face: BMFace object
        uv_layer: BMesh UV layer

    Returns:
        Absolute UV area (always positive)
    """
    uvs = [loop[uv_layer].uv for loop in face.loops]
    n = len(uvs)
    if n < 3:
        return 0.0

    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += uvs[i].x * uvs[j].y
        area -= uvs[j].x * uvs[i].y

    return abs(area / 2.0)


def compute_texel_densities(bm, uv_layer, island_faces):
    """
    Compute texel density ratio for each face in an island.

    Texel density = 3D_area / UV_area
    Higher values mean the face is more compressed in UV space.

    Args:
        bm: BMesh object
        uv_layer: BMesh UV layer
        island_faces: Set of face indices in the island

    Returns:
        Dict mapping face_idx -> density ratio
    """
    densities = {}

    for face_idx in island_faces:
        face = bm.faces[face_idx]

        area_3d = face.calc_area()
        area_uv = compute_face_uv_area(face, uv_layer)

        # Avoid division by zero
        if area_uv < MIN_UV_AREA:
            # Extremely compressed - assign very high density
            densities[face_idx] = float("inf")
        else:
            densities[face_idx] = area_3d / area_uv

    return densities


def compute_texel_densities_numpy(bm, uv_layer, island_faces):
    """
    NumPy-accelerated texel density computation.

    Args:
        bm: BMesh object
        uv_layer: BMesh UV layer
        island_faces: Set of face indices in the island

    Returns:
        Dict mapping face_idx -> density ratio
    """
    face_list = list(island_faces)
    n_faces = len(face_list)

    if n_faces == 0:
        return {}

    # Collect areas
    areas_3d = np.zeros(n_faces)
    areas_uv = np.zeros(n_faces)

    for i, face_idx in enumerate(face_list):
        face = bm.faces[face_idx]
        areas_3d[i] = face.calc_area()
        areas_uv[i] = compute_face_uv_area(face, uv_layer)

    # Avoid division by zero
    areas_uv = np.maximum(areas_uv, MIN_UV_AREA)

    # Compute densities
    densities_arr = areas_3d / areas_uv

    # Convert to dict
    return {face_list[i]: densities_arr[i] for i in range(n_faces)}


def compute_per_face_shape_distortion(bm, uv_layer, island_faces):
    """
    Compute per-face shape distortion by comparing 3D vs 2D edge length ratios.

    For each face:
    - Get 3D edge lengths [L1, L2, L3]
    - Get 2D (UV) edge lengths [l1, l2, l3]
    - Compute ratios [L1/l1, L2/l2, L3/l3]
    - Compute coefficient of variation (std/mean) of these ratios

    Low CV = face has uniform scaling (good)
    High CV = face has uneven stretching (bad, vortex indicator)

    Args:
        bm: BMesh object
        uv_layer: BMesh UV layer
        island_faces: Set of face indices

    Returns:
        Dict with stats: max_cv, avg_cv, worst_face_idx, face_cvs dict
    """
    face_cvs = {}

    for face_idx in island_faces:
        if face_idx >= len(bm.faces):
            continue
        face = bm.faces[face_idx]

        ratios_3d_to_2d = []

        for loop in face.loops:
            edge = loop.edge

            length_3d = edge.calc_length()

            uv_coords = []
            for vert in edge.verts:
                for face_loop in face.loops:
                    if face_loop.vert == vert:
                        uv_coords.append(face_loop[uv_layer].uv.copy())
                        break

            if len(uv_coords) == 2:
                length_uv = (uv_coords[0] - uv_coords[1]).length

                if length_uv < 1e-12:
                    ratios_3d_to_2d.append(float("inf"))
                elif length_3d < 1e-12:
                    ratios_3d_to_2d.append(0)
                else:
                    ratios_3d_to_2d.append(length_3d / length_uv)

        if len(ratios_3d_to_2d) < 2:
            continue

        finite_ratios = [r for r in ratios_3d_to_2d if r != float("inf") and r > 0]

        if len(finite_ratios) < 2:
            face_cvs[face_idx] = float("inf")
            continue

        mean_ratio = sum(finite_ratios) / len(finite_ratios)
        if mean_ratio < 1e-12:
            face_cvs[face_idx] = float("inf")
            continue

        variance = sum((r - mean_ratio) ** 2 for r in finite_ratios) / len(
            finite_ratios
        )
        std_dev = variance**0.5
        cv = std_dev / mean_ratio

        face_cvs[face_idx] = cv

    if not face_cvs:
        return {
            "max_cv": 0,
            "avg_cv": 0,
            "worst_face_idx": -1,
            "face_cvs": {},
            "num_faces": 0,
        }

    finite_cvs = [cv for cv in face_cvs.values() if cv != float("inf")]

    if not finite_cvs:
        worst_face = max(
            face_cvs.keys(), key=lambda k: 1 if face_cvs[k] == float("inf") else 0
        )
        return {
            "max_cv": float("inf"),
            "avg_cv": float("inf"),
            "worst_face_idx": worst_face,
            "face_cvs": face_cvs,
            "num_faces": len(face_cvs),
        }

    max_cv = max(finite_cvs)
    avg_cv = sum(finite_cvs) / len(finite_cvs)
    worst_face = max(
        face_cvs.keys(),
        key=lambda k: face_cvs[k] if face_cvs[k] != float("inf") else -1,
    )

    has_inf = any(cv == float("inf") for cv in face_cvs.values())
    if has_inf:
        worst_face = next(k for k, v in face_cvs.items() if v == float("inf"))
        max_cv = float("inf")

    return {
        "max_cv": max_cv,
        "avg_cv": avg_cv,
        "worst_face_idx": worst_face,
        "face_cvs": face_cvs,
        "num_faces": len(face_cvs),
    }


def is_island_vortex(
    island_faces,
    densities,
    shape_stats=None,
    density_threshold=VORTEX_DENSITY_RATIO_THRESHOLD,
    shape_cv_threshold=VORTEX_SHAPE_CV_THRESHOLD,
):
    """
    Check if an island has vortex distortion.

    A vortex is detected when:
    1. The ratio of max to min face density exceeds threshold, OR
    2. The max per-face shape distortion CV exceeds threshold

    Args:
        island_faces: Set of face indices
        densities: Dict of face_idx -> density
        shape_stats: Dict from compute_per_face_shape_distortion (max_cv, avg_cv, etc.)
        density_threshold: Max/min density ratio threshold
        shape_cv_threshold: Max coefficient of variation threshold

    Returns:
        Tuple of (is_vortex: bool, density_ratio: float, max_shape_cv: float)
    """
    if len(island_faces) < 2:
        return False, 0.0, 0.0

    island_densities = [densities[f] for f in island_faces if f in densities]

    if not island_densities:
        return False, 0.0, 0.0

    # Filter out infinities for ratio calculation
    finite_densities = [d for d in island_densities if d != float("inf")]

    density_ratio = 0.0
    if len(finite_densities) >= 2:
        min_density = min(finite_densities)
        max_density = max(finite_densities)

        if min_density <= 0:
            density_ratio = float("inf")
        else:
            density_ratio = max_density / min_density
    elif len([d for d in island_densities if d == float("inf")]) > 0:
        density_ratio = float("inf")

    # Check per-face shape distortion (CV)
    max_shape_cv = 0.0
    if shape_stats:
        max_shape_cv = shape_stats.get("max_cv", 0.0)

    # Vortex if either metric exceeds threshold
    is_vortex = (density_ratio > density_threshold) or (
        max_shape_cv > shape_cv_threshold
    )

    return is_vortex, density_ratio, max_shape_cv


def find_vortex_center(island_faces, densities, bm=None, uv_layer=None):
    """
    Find the face at the center of the vortex (highest density / most compressed).

    Args:
        island_faces: Set of face indices
        densities: Dict of face_idx -> density
        bm: Optional BMesh for UV position logging
        uv_layer: Optional UV layer for UV position logging

    Returns:
        Face index with highest density, or None
    """
    if not island_faces:
        return None

    # Find face with maximum density (most compressed in UV)
    max_density = -1
    center_face = None

    for face_idx in island_faces:
        density = densities.get(face_idx, 0)
        if density > max_density:
            max_density = density
            center_face = face_idx

    return center_face


def is_edge_uv_discontinuous(edge, uv_layer, island_faces):
    """
    Check if an edge has UV discontinuity (is on the Island Boundary).

    Asks the UV directly: an edge is on the boundary if its UV coordinates
    don't match between the two faces sharing it.

    Args:
        edge: BMEdge object
        uv_layer: BMesh UV layer
        island_faces: Set of face indices in the island

    Returns:
        True if edge is on island boundary, False otherwise
    """
    # Mesh boundary - only 1 face
    if len(edge.link_faces) == 1:
        return True

    # Get the two faces sharing this edge
    face1, face2 = edge.link_faces[0], edge.link_faces[1]

    # One face outside island = boundary
    if face1.index not in island_faces or face2.index not in island_faces:
        return True

    # Get UV coords for this edge's vertices from both faces
    def get_edge_uvs(face):
        uvs = {}
        for loop in face.loops:
            if loop.vert in edge.verts:
                uvs[loop.vert.index] = loop[uv_layer].uv.copy()
        return uvs

    uvs1 = get_edge_uvs(face1)
    uvs2 = get_edge_uvs(face2)

    # Check if UVs match at both vertices
    for vert_idx in uvs1:
        if vert_idx in uvs2:
            if (uvs1[vert_idx] - uvs2[vert_idx]).length > 1e-6:
                return True  # UV discontinuity = boundary

    return False  # Continuous UVs = not boundary


def find_island_boundary_vertices(bm, island_faces, uv_layer, seams_to_ignore=None):
    """
    Find all vertices on the UV island's perimeter (Island Boundary).

    Asks the UV directly: an edge is on the boundary if its UV coordinates
    are discontinuous between the two faces sharing it.

    Args:
        bm: BMesh object
        island_faces: Set of face indices in the island
        uv_layer: BMesh UV layer
        seams_to_ignore: Set of edge indices to NOT count as boundary (seams we just added)

    Returns:
        Set of vertex indices on the island boundary
    """
    boundary_verts = set()
    seams_to_ignore = seams_to_ignore or set()
    checked_edges = set()
    discontinuous_count = 0

    for face_idx in island_faces:
        face = bm.faces[face_idx]
        for loop in face.loops:
            edge = loop.edge

            # Skip already checked edges
            if edge.index in checked_edges:
                continue
            checked_edges.add(edge.index)

            # Skip edges we added as seams this session (we want to cut TO existing boundary)
            if edge.index in seams_to_ignore:
                continue

            # Ask UV directly: is this edge discontinuous?
            if is_edge_uv_discontinuous(edge, uv_layer, island_faces):
                boundary_verts.add(edge.verts[0].index)
                boundary_verts.add(edge.verts[1].index)
                discontinuous_count += 1

    return boundary_verts


def find_shortest_path_dijkstra(bm, start_vert_idx, boundary_verts, island_faces):
    """
    Dijkstra's algorithm to find shortest path from start vertex to any boundary vertex.

    Path cost = sum of 3D edge lengths (stable metric regardless of UV distortion).

    Args:
        bm: BMesh object
        start_vert_idx: Starting vertex index (from the crushed face)
        boundary_verts: Set of vertex indices on the island boundary
        island_faces: Set of face indices in the island

    Returns:
        List of edge indices forming the shortest path, or empty list if no path
    """
    import heapq

    # Build set of vertices in island (for constraining the search)
    island_verts = set()
    for face_idx in island_faces:
        face = bm.faces[face_idx]
        for vert in face.verts:
            island_verts.add(vert.index)

    # If start is already on boundary, return empty (no cut needed from this vertex)
    if start_vert_idx in boundary_verts:
        return []

    # Dijkstra: (distance, vert_idx, edge_that_led_here)
    # Priority queue: (distance, counter, vert_idx)
    INF = float("inf")
    dist = {v: INF for v in island_verts}
    dist[start_vert_idx] = 0.0
    parent = {}  # vert_idx -> (parent_vert_idx, edge_idx)
    counter = 0  # Tie-breaker for heap

    heap = [(0.0, counter, start_vert_idx)]

    while heap:
        d, _, u = heapq.heappop(heap)

        if d > dist[u]:
            continue  # Stale entry

        # Check if we reached a boundary vertex
        if u in boundary_verts:
            # Trace back path
            edge_path = []
            current = u
            while current in parent:
                parent_vert, edge_idx = parent[current]
                edge_path.append(edge_idx)
                current = parent_vert
            return edge_path

        # Explore neighbors
        vert = bm.verts[u]
        for edge in vert.link_edges:
            # Get the other vertex
            other_vert = edge.other_vert(vert)
            v = other_vert.index

            # Only consider vertices in the island
            if v not in island_verts:
                continue

            # Cost = 3D edge length
            edge_length = edge.calc_length()
            new_dist = dist[u] + edge_length

            if new_dist < dist[v]:
                dist[v] = new_dist
                parent[v] = (u, edge.index)
                counter += 1
                heapq.heappush(heap, (new_dist, counter, v))

    # No path found
    return []


def walk_to_boundary(bm, island_faces, uv_layer, start_face_idx, seam_tracker=None):
    """
    Find shortest path from vortex center to island boundary using Dijkstra.

    Pure 2D algorithm:
    1. Find the crushed face (vortex center) - passed as start_face_idx
    2. Pick a vertex from that face
    3. Find all Island Boundary vertices (UV discontinuities)
    4. Dijkstra shortest path (by 3D edge length) to nearest boundary vertex
    5. Return edge path for seam cutting

    Args:
        bm: BMesh object
        island_faces: Set of face indices in this island
        uv_layer: BMesh UV layer
        start_face_idx: Face index to start from (vortex center / crushed face)
        seam_tracker: Set of edge indices we added this session (ignore as boundary)

    Returns:
        List of edge indices forming shortest path to island boundary
    """
    # Get boundary vertices by checking UV discontinuity (excluding seams we added)
    boundary_verts = find_island_boundary_vertices(
        bm, island_faces, uv_layer, seam_tracker
    )

    if not boundary_verts:
        return []

    # Pick a vertex from the crushed face
    start_face = bm.faces[start_face_idx]
    start_vert = start_face.verts[0]  # Any vertex from the crushed face

    # Try Dijkstra from this vertex
    edge_path = find_shortest_path_dijkstra(
        bm, start_vert.index, boundary_verts, island_faces
    )

    # If no path from first vertex, try other vertices of the face
    if not edge_path:
        for vert in start_face.verts[1:]:
            edge_path = find_shortest_path_dijkstra(
                bm, vert.index, boundary_verts, island_faces
            )
            if edge_path:
                break

    return edge_path


def get_bootstrap_seam_edges(bm, island_faces):
    """
    Get exactly 2 contiguous edges from an island that are NOT already seams.

    ONLY for bootstrapping a mesh that has never been unwrapped. When a mesh has
    zero seams, Blender's unwrap operator may fail or produce degenerate results.
    This provides the minimum 2 seams needed to bootstrap the unwrap process.

    Args:
        bm: BMesh object
        island_faces: Set of face indices

    Returns:
        List of exactly 2 edge indices, or empty list if not possible
    """
    if not island_faces:
        return []

    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Iterate through all faces in island looking for 2 contiguous non-seam edges
    for face_idx in island_faces:
        if face_idx >= len(bm.faces):
            continue
        face = bm.faces[face_idx]
        edges = [loop.edge for loop in face.loops]

        # Find 2 contiguous edges that are not already seams
        non_seam_edges = [e for e in edges if not e.seam]

        if len(non_seam_edges) >= 2:
            # Check if any two are contiguous (share a vertex)
            for i, e1 in enumerate(non_seam_edges):
                for e2 in non_seam_edges[i + 1 :]:
                    v1 = set(e1.verts)
                    v2 = set(e2.verts)
                    if v1 & v2:  # Share a vertex = contiguous
                        return [e1.index, e2.index]

    # No suitable edges found in any face
    return []


def find_boundary_loops(bm, island_faces, uv_layer):
    """
    Find all separate boundary loops in an island.

    A boundary loop is a connected component of boundary edges. An island
    can have multiple loops (e.g., a donut has inner and outer boundaries).

    Args:
        bm: BMesh object
        island_faces: Set of face indices in the island
        uv_layer: BMesh UV layer

    Returns:
        List of sets, each set containing vertex indices of one boundary loop
    """
    # First find all boundary edges
    boundary_edges = set()
    checked_edges = set()

    for face_idx in island_faces:
        face = bm.faces[face_idx]
        for loop in face.loops:
            edge = loop.edge
            if edge.index in checked_edges:
                continue
            checked_edges.add(edge.index)

            if is_edge_uv_discontinuous(edge, uv_layer, island_faces):
                boundary_edges.add(edge.index)

    if not boundary_edges:
        return []

    # Build adjacency: vertex -> set of connected boundary vertices
    vert_adjacency = {}
    for edge_idx in boundary_edges:
        edge = bm.edges[edge_idx]
        v0, v1 = edge.verts[0].index, edge.verts[1].index
        if v0 not in vert_adjacency:
            vert_adjacency[v0] = set()
        if v1 not in vert_adjacency:
            vert_adjacency[v1] = set()
        vert_adjacency[v0].add(v1)
        vert_adjacency[v1].add(v0)

    # Find connected components using BFS
    all_boundary_verts = set(vert_adjacency.keys())
    visited = set()
    loops = []

    while all_boundary_verts - visited:
        start = next(iter(all_boundary_verts - visited))
        component = set()
        queue = [start]

        while queue:
            v = queue.pop(0)
            if v in visited:
                continue
            visited.add(v)
            component.add(v)
            for neighbor in vert_adjacency.get(v, []):
                if neighbor not in visited:
                    queue.append(neighbor)

        if component:
            loops.append(component)

    return loops


def connect_boundary_loops(bm, island_faces, uv_layer, loops, seam_tracker):
    """
    Connect multiple boundary loops by adding seams between them.

    If an island has multiple disconnected boundaries (e.g., inner/outer rings),
    this adds seams to connect them into a single contiguous boundary.

    Args:
        bm: BMesh object
        island_faces: Set of face indices
        uv_layer: BMesh UV layer
        loops: List of boundary loop vertex sets (from find_boundary_loops)
        seam_tracker: Set to track added seams

    Returns:
        Number of seams added
    """
    if len(loops) <= 1:
        return 0

    seams_added = 0

    # Connect each additional loop to the first (main) loop
    main_loop = loops[0]

    for other_loop in loops[1:]:
        # Find shortest path from any vertex in other_loop to any vertex in main_loop
        best_path = None
        best_length = float("inf")

        # Try a few vertices from the other loop to find a good path
        sample_verts = list(other_loop)[:5]  # Sample up to 5 vertices

        for start_vert_idx in sample_verts:
            path = find_shortest_path_dijkstra(
                bm, start_vert_idx, main_loop, island_faces
            )
            if path:
                # Calculate path length
                path_length = sum(bm.edges[e_idx].calc_length() for e_idx in path)
                if path_length < best_length:
                    best_length = path_length
                    best_path = path

        if best_path:
            mark_edges_as_seam(bm, best_path, seam_tracker)
            seams_added += len(best_path)
            # Merge other_loop into main_loop so subsequent loops connect to enlarged set
            main_loop = main_loop | other_loop

    return seams_added


def mark_edges_as_seam(bm, edge_indices, seam_tracker=None):
    """
    Mark edges as seams, optionally tracking which ones we changed.

    Args:
        bm: BMesh object
        edge_indices: List of edge indices to mark
        seam_tracker: Set to add newly seamed edge indices to (None = don't track)
    """
    bm.edges.ensure_lookup_table()

    for edge_idx in edge_indices:
        if edge_idx < len(bm.edges):
            edge = bm.edges[edge_idx]
            if not edge.seam:
                edge.seam = True
                if seam_tracker is not None:
                    seam_tracker.add(edge_idx)


def restore_original_seams(bm, seam_tracker):
    """
    Restore edges to unseamed state.

    Args:
        bm: BMesh object
        seam_tracker: Set of edge indices we seamed
    """
    bm.edges.ensure_lookup_table()

    for edge_idx in seam_tracker:
        if edge_idx < len(bm.edges):
            bm.edges[edge_idx].seam = False


def unwrap_island_minimum_stretch(context, mesh_obj, bm, island_faces, uv_layer, uv_layer_index):
    """
    Unwrap an island using Blender's Minimum Stretch method.

    Args:
        context: Blender context
        mesh_obj: Mesh object
        bm: BMesh (will be updated to mesh before unwrap)
        island_faces: Set of face indices
        uv_layer: BMesh UV layer
        uv_layer_index: Index of the UV layer to unwrap (operators work on active layer)

    Returns:
        True if unwrap changed UVs, False otherwise
    """
    # Store original UVs to detect if unwrap changed anything
    original_uvs = {}
    for face_idx in island_faces:
        face = bm.faces[face_idx]
        for loop in face.loops:
            key = (face_idx, loop.vert.index)
            original_uvs[key] = loop[uv_layer].uv.copy()

    # Write bmesh to mesh for operator
    bm.to_mesh(mesh_obj.data)

    # Enter edit mode
    bpy.ops.object.mode_set(mode="OBJECT")
    context.view_layer.objects.active = mesh_obj
    mesh_obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    # Deselect all faces first
    bpy.ops.mesh.select_all(action="DESELECT")

    # Select island faces
    bpy.ops.object.mode_set(mode="OBJECT")

    for face_idx in island_faces:
        if face_idx < len(mesh_obj.data.polygons):
            mesh_obj.data.polygons[face_idx].select = True

    bpy.ops.object.mode_set(mode="EDIT")

    # Count seams before unwrap
    seam_count = sum(1 for e in mesh_obj.data.edges if e.use_seam)

    # Set the correct UV layer as active before unwrap (operator works on active layer)
    mesh_obj.data.uv_layers.active_index = uv_layer_index

    # Unwrap with minimum stretch
    try:
        bpy.ops.uv.unwrap(method="MINIMUM_STRETCH", margin=0.001)
    except RuntimeError:
        pass

    # Return to object mode
    bpy.ops.object.mode_set(mode="OBJECT")

    # Reload bmesh from mesh
    bm.clear()
    bm.from_mesh(mesh_obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # Get new UV layer reference
    uv_layer_new = bm.loops.layers.uv.active

    # Check if UVs changed
    changed = False
    for face_idx in island_faces:
        if face_idx >= len(bm.faces):
            continue
        face = bm.faces[face_idx]
        for loop in face.loops:
            key = (face_idx, loop.vert.index)
            if key in original_uvs:
                old_uv = original_uvs[key]
                new_uv = loop[uv_layer_new].uv
                if (old_uv - new_uv).length > 1e-6:
                    changed = True
                    break
        if changed:
            break

    return changed, uv_layer_new


def repair_vortex_island(
    context,
    mesh_obj,
    bm,
    uv_layer,
    uv_layer_index,
    island_faces,
    max_iterations=MAX_VORTEX_ITERATIONS,
    restore_seams=False,
):
    """
    Main repair loop for a vortex island.

    Args:
        context: Blender context
        mesh_obj: Mesh object
        bm: BMesh object
        uv_layer: BMesh UV layer
        uv_layer_index: Index of the UV layer (for operator calls)
        island_faces: Set of face indices
        max_iterations: Maximum repair iterations
        restore_seams: If True, remove seams we added after fixing (default False for debug)

    Returns:
        Tuple of (fixed: bool, iterations_used: int, uv_layer: updated layer)
    """
    seam_tracker = set()
    current_uv_layer = uv_layer

    # Unify multiple boundary loops before starting vortex repair
    # (e.g., donut shapes have inner/outer boundaries that need connecting)
    boundary_loops = find_boundary_loops(bm, island_faces, current_uv_layer)
    if len(boundary_loops) > 1:
        loops_connected = connect_boundary_loops(
            bm, island_faces, current_uv_layer, boundary_loops, seam_tracker
        )
        if loops_connected > 0:
            bm.to_mesh(mesh_obj.data)
            # Re-unwrap after connecting loops
            changed, current_uv_layer = unwrap_island_minimum_stretch(
                context, mesh_obj, bm, island_faces, current_uv_layer, uv_layer_index
            )

    cut_count = 0  # Count actual seam cuts, not loop iterations
    consecutive_failures = 0  # Track consecutive loops without progress
    MAX_CONSECUTIVE_FAILURES = 20  # Safety limit

    while cut_count < max_iterations:
        # Compute current densities and shape distortion
        densities = compute_texel_densities_numpy(bm, current_uv_layer, island_faces)
        shape_stats = compute_per_face_shape_distortion(
            bm, current_uv_layer, island_faces
        )

        # Check if still a vortex
        is_vortex, density_ratio, max_shape_cv = is_island_vortex(
            island_faces, densities, shape_stats
        )

        if not is_vortex:
            # Fixed! Restore seams if requested
            if restore_seams:
                restore_original_seams(bm, seam_tracker)
            return True, cut_count, current_uv_layer

        # Try unwrap
        changed, current_uv_layer = unwrap_island_minimum_stretch(
            context, mesh_obj, bm, island_faces, current_uv_layer, uv_layer_index
        )

        if not changed:
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                break
            # Continue to next iteration - try finding a new path
            # (Don't add random seams, that's not the solution)

        # Recompute densities and shape after unwrap
        densities = compute_texel_densities_numpy(bm, current_uv_layer, island_faces)
        shape_stats = compute_per_face_shape_distortion(
            bm, current_uv_layer, island_faces
        )

        # Check if fixed
        is_vortex, density_ratio, max_shape_cv = is_island_vortex(
            island_faces, densities, shape_stats
        )
        if not is_vortex:
            if restore_seams:
                restore_original_seams(bm, seam_tracker)
            return True, cut_count, current_uv_layer

        # Still a vortex - find center and walk to boundary
        center_face = find_vortex_center(
            island_faces, densities, bm=bm, uv_layer=current_uv_layer
        )

        if center_face is None:
            break

        edge_path = walk_to_boundary(
            bm, island_faces, current_uv_layer, center_face, seam_tracker
        )

        if not edge_path:
            # Dijkstra couldn't find a path to boundary - continue and let
            # consecutive_failures eventually end the loop
            consecutive_failures += 1
            continue

        # Mark the path edges as seams
        mark_edges_as_seam(bm, edge_path, seam_tracker)
        bm.to_mesh(mesh_obj.data)

        # Increment cut count AFTER making a cut
        cut_count += 1
        consecutive_failures = 0  # Reset on success

    # Max cuts reached - restore seams if requested
    if restore_seams:
        restore_original_seams(bm, seam_tracker)
    return False, cut_count, current_uv_layer


def detect_and_fix_vortex_islands(
    context, mesh_obj, uv_layer_index, restore_seams=False
):
    """
    Bootstrap mesh unwrapping, detect all UV islands, and repair vortex ones.

    Vortex islands are UV patterns with severe distortion (spiraling inward).

    Args:
        context: Blender context
        mesh_obj: Mesh object
        uv_layer_index: UV layer index to work with
        restore_seams: If True, remove seams we added after fixing (default False for debug)

    Returns:
        Dict with stats: {islands_checked, vortexes_found, vortexes_fixed}
    """
    from .auto_fix_uvs import detect_uv_islands

    mesh_data = mesh_obj.data

    # Work with bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    uv_layer = bm.loops.layers.uv[uv_layer_index]

    current_uv_layer = uv_layer

    # Detect islands from current UVs (no global unwrap)
    islands = detect_uv_islands(bm, current_uv_layer)

    # Per-island bootstrap: add seams only to islands with 0 boundary loops OR degenerate UVs
    bootstrapped_faces = set()
    for island in islands:
        num_loops = len(find_boundary_loops(bm, island, current_uv_layer))
        densities = compute_texel_densities_numpy(bm, current_uv_layer, island)
        max_density = max(densities.values()) if densities else 0
        is_degenerate = num_loops == 0 or max_density == float("inf")

        if is_degenerate:
            bootstrap_edges = get_bootstrap_seam_edges(bm, island)
            if bootstrap_edges:
                mark_edges_as_seam(bm, bootstrap_edges, seam_tracker=None)
                bootstrapped_faces.update(island)

    if bootstrapped_faces:
        bm.to_mesh(mesh_data)

        # Unwrap only the bootstrapped islands, not the whole mesh
        _, current_uv_layer = unwrap_island_minimum_stretch(
            context, mesh_obj, bm, bootstrapped_faces, current_uv_layer, uv_layer_index
        )

        # Reload bmesh after unwrap
        bm.clear()
        bm.from_mesh(mesh_data)
        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        # Re-acquire the UV layer by its original index
        current_uv_layer = bm.loops.layers.uv[uv_layer_index]

        # Re-detect islands after bootstrap unwrap
        islands = detect_uv_islands(bm, current_uv_layer)

    stats = {
        "islands_checked": len(islands),
        "vortexes_found": 0,
        "vortexes_fixed": 0,
        "island_metrics": [],  # Per-island density_ratio, edge_ratio, is_vortex for report
    }

    # Process each island for vortex detection and fix
    for island_idx, island in enumerate(islands):
        # Compute densities and shape distortion
        densities = compute_texel_densities_numpy(bm, current_uv_layer, island)
        shape_stats = compute_per_face_shape_distortion(bm, current_uv_layer, island)

        # Check for vortex
        is_vortex, density_ratio, max_shape_cv = is_island_vortex(
            island, densities, shape_stats
        )

        stats["island_metrics"].append(
            {
                "density_ratio": float(density_ratio),
                "max_shape_cv": float(max_shape_cv),
                "avg_shape_cv": float(shape_stats.get("avg_cv", 0)),
                "is_vortex": is_vortex,
            }
        )

        if is_vortex:
            stats["vortexes_found"] += 1

            # Attempt fix
            fixed, iterations, current_uv_layer = repair_vortex_island(
                context,
                mesh_obj,
                bm,
                current_uv_layer,
                uv_layer_index,
                island,
                restore_seams=restore_seams,
            )

            if fixed:
                stats["vortexes_fixed"] += 1

    # Write final state back to mesh
    bm.to_mesh(mesh_data)
    bm.free()

    return stats
