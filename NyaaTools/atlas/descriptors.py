"""
Descriptor classes for atlas configuration.

Provides dataclasses representing:
- IslandDescriptor: Individual UV islands within a material
- MaterialDescriptor: Complete material atlas configuration
- AtlasDescriptor: Full atlas state with all materials

These descriptors serve as the in-memory representation of atlas
configuration, bridging between PropertyGroup storage and runtime
manipulation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Any, Set
import bpy
import bmesh
import math

from .stratum import (
    stratum_to_scale,
    stratum_to_grid_size,
    tile_to_uv_offset,
    get_tile_bounds,
    validate_tile_position,
    promote_tile_coords,
    demote_tile_coords,
    calculate_recommended_stratum,
    calculate_texel_significance,
    StratumGrid,
)


# -----------------------------------------------------------------------------
# Island Descriptor
# -----------------------------------------------------------------------------


@dataclass
class IslandDescriptor:
    """
    Represents a single UV island within a material.
    
    Islands are detected using Blender's built-in UV island detection.
    Each island tracks its UV bounds, texel metrics, and position within
    the parent material's tile.
    
    Attributes:
        island_id: Unique identifier for this island
        mesh_name: Name of the source mesh object
        material_name: Name of the parent material
        face_indices: Polygon indices belonging to this island
        loop_indices: Loop indices for UV access
        bounds_min: (u_min, v_min) in material's 0-1 UV space
        bounds_max: (u_max, v_max) in material's 0-1 UV space
        uv_area: Total UV space area of the island
        world_area: Total world space surface area
        texel_density: Pixels per world unit (computed)
        significance: Weight for auto-placement (0.0-1.0)
        local_offset: Offset within parent tile (0-1 relative)
        local_scale: Scale within parent tile (default 1.0, 1.0)
    """
    
    # Identity
    island_id: str = ""
    mesh_name: str = ""
    material_name: str = ""
    
    # Geometry references
    face_indices: List[int] = field(default_factory=list)
    loop_indices: List[int] = field(default_factory=list)
    
    # UV bounds (in material's 0-1 space)
    bounds_min: Tuple[float, float] = (0.0, 0.0)
    bounds_max: Tuple[float, float] = (1.0, 1.0)
    
    # Texel metrics
    uv_area: float = 0.0
    world_area: float = 0.0
    texel_density: float = 0.0
    significance: float = 0.0
    
    # Local positioning within material's tile
    local_offset: Tuple[float, float] = (0.0, 0.0)
    local_scale: Tuple[float, float] = (1.0, 1.0)
    
    # UI callbacks (optional, set by panel system)
    on_resize: Optional[Callable[[float, float], None]] = field(default=None, repr=False)
    on_reposition: Optional[Callable[[float, float], None]] = field(default=None, repr=False)
    
    @property
    def bounds_size(self) -> Tuple[float, float]:
        """Get the size of the island bounds."""
        return (
            self.bounds_max[0] - self.bounds_min[0],
            self.bounds_max[1] - self.bounds_min[1],
        )
    
    @property
    def bounds_center(self) -> Tuple[float, float]:
        """Get the center of the island bounds."""
        return (
            (self.bounds_min[0] + self.bounds_max[0]) / 2,
            (self.bounds_min[1] + self.bounds_max[1]) / 2,
        )
    
    def set_local_position(self, offset: Tuple[float, float]) -> None:
        """Set the local offset and trigger callback."""
        self.local_offset = offset
        if self.on_reposition:
            self.on_reposition(offset[0], offset[1])
    
    def set_local_scale(self, scale: Tuple[float, float]) -> None:
        """Set the local scale and trigger callback."""
        self.local_scale = scale
        if self.on_resize:
            self.on_resize(scale[0], scale[1])


# -----------------------------------------------------------------------------
# Material Descriptor
# -----------------------------------------------------------------------------


@dataclass
class MaterialDescriptor:
    """
    Represents a material's atlas configuration.
    
    Each material occupies a tile at a specific stratum level. The descriptor
    tracks the material's placement, associated meshes, islands, and captured
    bake images.
    
    Attributes:
        material_name: Name of the Blender material
        source_mesh_names: Names of mesh objects using this material
        stratum: Mipmap level (0 = full, higher = smaller)
        tile_x: X position in stratum grid
        tile_y: Y position in stratum grid
        islands: List of UV islands within this material
        total_uv_area: Aggregate UV space area
        total_world_area: Aggregate world space surface area
        recommended_stratum: Auto-calculated optimal stratum
        captured_images: Dict of format -> intermediate bake image
    """
    
    # Identity
    material_name: str = ""
    source_mesh_names: List[str] = field(default_factory=list)
    
    # Stratum placement
    stratum: int = 0
    tile_x: int = 0
    tile_y: int = 0
    
    # Islands
    islands: List[IslandDescriptor] = field(default_factory=list)
    
    # Aggregate metrics
    total_uv_area: float = 0.0
    total_world_area: float = 0.0
    total_face_count: int = 0
    recommended_stratum: int = 0
    significance: float = 0.0
    
    # Bake state
    captured_images: Dict[str, bpy.types.Image] = field(default_factory=dict)
    
    # UI callbacks (optional, set by panel system)
    on_stratum_change: Optional[Callable[[int], None]] = field(default=None, repr=False)
    on_tile_change: Optional[Callable[[int, int], None]] = field(default=None, repr=False)
    on_drag_start: Optional[Callable[[], None]] = field(default=None, repr=False)
    on_drag_end: Optional[Callable[[int, int, int], None]] = field(default=None, repr=False)
    
    @property
    def uv_scale(self) -> float:
        """Get the UV scale factor for this material's stratum."""
        return stratum_to_scale(self.stratum)
    
    @property
    def uv_offset(self) -> Tuple[float, float]:
        """Get the UV offset for this material's tile position."""
        return tile_to_uv_offset(self.stratum, self.tile_x, self.tile_y)
    
    @property
    def tile_bounds(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Get the UV bounds for this material's tile."""
        return get_tile_bounds(self.stratum, self.tile_x, self.tile_y)
    
    def get_material(self) -> Optional[bpy.types.Material]:
        """Get the Blender material object."""
        return bpy.data.materials.get(self.material_name)
    
    def get_source_meshes(self) -> List[bpy.types.Object]:
        """Get the Blender mesh objects using this material."""
        meshes = []
        for name in self.source_mesh_names:
            obj = bpy.data.objects.get(name)
            if obj and obj.type == "MESH":
                meshes.append(obj)
        return meshes
    
    def promote(self, grid: Optional[StratumGrid] = None) -> bool:
        """
        Promote to a higher-resolution stratum (lower number).
        
        Args:
            grid: Optional StratumGrid for occupancy validation
            
        Returns:
            True if promotion succeeded, False if at stratum 0 or blocked
        """
        if self.stratum <= 0:
            return False
        
        new_stratum, new_tx, new_ty = promote_tile_coords(
            self.stratum, self.tile_x, self.tile_y
        )
        
        # Check if new position is free (if grid provided)
        if grid is not None:
            # Release current tile first
            grid.release_tile(self.stratum, self.tile_x, self.tile_y)
            
            if not grid.is_tile_free(new_stratum, new_tx, new_ty):
                # Re-occupy original tile
                grid.occupy_tile(self.stratum, self.tile_x, self.tile_y)
                return False
            
            grid.occupy_tile(new_stratum, new_tx, new_ty)
        
        self.stratum = new_stratum
        self.tile_x = new_tx
        self.tile_y = new_ty
        
        if self.on_stratum_change:
            self.on_stratum_change(self.stratum)
        
        return True
    
    def demote(self, grid: Optional[StratumGrid] = None, max_stratum: int = 8) -> bool:
        """
        Demote to a lower-resolution stratum (higher number).
        
        Args:
            grid: Optional StratumGrid for occupancy validation
            max_stratum: Maximum stratum level allowed
            
        Returns:
            True if demotion succeeded, False if at max stratum or blocked
        """
        if self.stratum >= max_stratum:
            return False
        
        new_stratum, new_tx, new_ty = demote_tile_coords(
            self.stratum, self.tile_x, self.tile_y, max_stratum
        )
        
        # Check if new position is free (if grid provided)
        if grid is not None:
            # Release current tile first
            grid.release_tile(self.stratum, self.tile_x, self.tile_y)
            
            if not grid.is_tile_free(new_stratum, new_tx, new_ty):
                # Re-occupy original tile
                grid.occupy_tile(self.stratum, self.tile_x, self.tile_y)
                return False
            
            grid.occupy_tile(new_stratum, new_tx, new_ty)
        
        self.stratum = new_stratum
        self.tile_x = new_tx
        self.tile_y = new_ty
        
        if self.on_stratum_change:
            self.on_stratum_change(self.stratum)
        
        return True
    
    def move_to_tile(
        self, 
        new_stratum: int, 
        new_tile_x: int, 
        new_tile_y: int,
        grid: Optional[StratumGrid] = None,
    ) -> bool:
        """
        Move to a specific tile position.
        
        Args:
            new_stratum: Target stratum level
            new_tile_x: Target X position
            new_tile_y: Target Y position
            grid: Optional StratumGrid for occupancy validation
            
        Returns:
            True if move succeeded, False if invalid or blocked
        """
        if not validate_tile_position(new_stratum, new_tile_x, new_tile_y):
            return False
        
        if grid is not None:
            # Release current tile
            grid.release_tile(self.stratum, self.tile_x, self.tile_y)
            
            if not grid.is_tile_free(new_stratum, new_tile_x, new_tile_y):
                # Re-occupy original tile
                grid.occupy_tile(self.stratum, self.tile_x, self.tile_y)
                return False
            
            grid.occupy_tile(new_stratum, new_tile_x, new_tile_y)
        
        self.stratum = new_stratum
        self.tile_x = new_tile_x
        self.tile_y = new_tile_y
        
        if self.on_tile_change:
            self.on_tile_change(new_tile_x, new_tile_y)
        
        return True
    
    def cleanup_captured_images(self) -> None:
        """Remove all captured intermediate images from Blender."""
        for format_name, image in list(self.captured_images.items()):
            if image and image.name in bpy.data.images:
                bpy.data.images.remove(image)
        self.captured_images.clear()


# -----------------------------------------------------------------------------
# Atlas Descriptor
# -----------------------------------------------------------------------------


@dataclass
class AtlasDescriptor:
    """
    Complete atlas configuration for an asset.
    
    Manages all materials, their placements, and the stratum grid state.
    Serves as the top-level container for atlas operations.
    
    Attributes:
        asset_name: Name of the parent asset
        atlas_width: Target atlas width in pixels
        atlas_height: Target atlas height in pixels
        materials: Dict of material_name -> MaterialDescriptor
        grid: StratumGrid tracking tile occupancy
        max_stratum: Maximum stratum depth
    """
    
    # Identity
    asset_name: str = ""
    
    # Resolution
    atlas_width: int = 4096
    atlas_height: int = 4096
    
    # Materials
    materials: Dict[str, MaterialDescriptor] = field(default_factory=dict)
    
    # Grid state
    grid: StratumGrid = field(default_factory=StratumGrid)
    max_stratum: int = 8
    
    def __post_init__(self):
        if self.grid is None:
            self.grid = StratumGrid(max_stratum=self.max_stratum)
    
    @property
    def coverage(self) -> float:
        """Get the atlas coverage ratio."""
        return self.grid.calculate_coverage()
    
    @property
    def material_count(self) -> int:
        """Get the number of materials in the atlas."""
        return len(self.materials)
    
    def add_material(self, descriptor: MaterialDescriptor) -> bool:
        """
        Add a material to the atlas.
        
        Args:
            descriptor: The MaterialDescriptor to add
            
        Returns:
            True if added successfully, False if material exists or tile blocked
        """
        if descriptor.material_name in self.materials:
            return False
        
        # Try to occupy the tile
        if not self.grid.occupy_tile(
            descriptor.stratum, descriptor.tile_x, descriptor.tile_y
        ):
            return False
        
        self.materials[descriptor.material_name] = descriptor
        return True
    
    def remove_material(self, material_name: str) -> Optional[MaterialDescriptor]:
        """
        Remove a material from the atlas.
        
        Args:
            material_name: Name of the material to remove
            
        Returns:
            The removed descriptor, or None if not found
        """
        if material_name not in self.materials:
            return None
        
        descriptor = self.materials.pop(material_name)
        self.grid.release_tile(descriptor.stratum, descriptor.tile_x, descriptor.tile_y)
        
        return descriptor
    
    def get_material(self, material_name: str) -> Optional[MaterialDescriptor]:
        """Get a material descriptor by name."""
        return self.materials.get(material_name)
    
    def get_materials_at_stratum(self, stratum: int) -> List[MaterialDescriptor]:
        """Get all materials at a specific stratum level."""
        return [m for m in self.materials.values() if m.stratum == stratum]
    
    def find_free_tile_for_stratum(self, stratum: int) -> Optional[Tuple[int, int]]:
        """Find a free tile at the specified stratum."""
        return self.grid.find_free_tile(stratum)
    
    def validate_no_overlaps(self) -> bool:
        """Check that no materials overlap."""
        # Rebuild grid from materials to verify
        test_grid = StratumGrid(max_stratum=self.max_stratum)
        
        for mat in self.materials.values():
            if not test_grid.occupy_tile(mat.stratum, mat.tile_x, mat.tile_y):
                return False
        
        return True
    
    def cleanup_all_captured_images(self) -> None:
        """Clean up all captured intermediate images."""
        for mat in self.materials.values():
            mat.cleanup_captured_images()
    
    def clear(self) -> None:
        """Clear all materials and reset the grid."""
        self.cleanup_all_captured_images()
        self.materials.clear()
        self.grid.clear()


# -----------------------------------------------------------------------------
# Builder Functions
# -----------------------------------------------------------------------------


def build_island_descriptors(
    mesh: bpy.types.Object,
    material_name: str,
    uv_layer_name: str = "UVMap",
) -> List[IslandDescriptor]:
    """
    Build island descriptors for a material on a mesh using Blender's island detection.
    
    Args:
        mesh: The mesh object
        material_name: Name of the material to analyze
        uv_layer_name: UV layer to use for island detection
        
    Returns:
        List of IslandDescriptor for each detected island
    """
    if mesh.type != "MESH":
        return []
    
    material = bpy.data.materials.get(material_name)
    if not material:
        return []
    
    # Find material index
    mat_index = -1
    for idx, mat_slot in enumerate(mesh.material_slots):
        if mat_slot.material == material:
            mat_index = idx
            break
    
    if mat_index < 0:
        return []
    
    # Get UV layer
    if uv_layer_name not in mesh.data.uv_layers:
        if not mesh.data.uv_layers:
            return []
        uv_layer_name = mesh.data.uv_layers[0].name
    
    # Use BMesh for island detection
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    bm.faces.ensure_lookup_table()
    
    uv_layer = bm.loops.layers.uv.get(uv_layer_name)
    if not uv_layer:
        bm.free()
        return []
    
    # Filter faces by material
    material_faces = [f for f in bm.faces if f.material_index == mat_index]
    if not material_faces:
        bm.free()
        return []
    
    # Detect islands using connected UV components
    islands = _detect_uv_islands_bmesh(bm, material_faces, uv_layer)
    
    # Build descriptors
    descriptors = []
    for idx, island_data in enumerate(islands):
        face_indices = island_data["face_indices"]
        loop_indices = island_data["loop_indices"]
        bounds_min = island_data["bounds_min"]
        bounds_max = island_data["bounds_max"]
        uv_area = island_data["uv_area"]
        world_area = island_data["world_area"]
        
        descriptor = IslandDescriptor(
            island_id=f"{mesh.name}_{material_name}_{idx}",
            mesh_name=mesh.name,
            material_name=material_name,
            face_indices=face_indices,
            loop_indices=loop_indices,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            uv_area=uv_area,
            world_area=world_area,
            texel_density=uv_area / world_area if world_area > 0 else 0,
            significance=calculate_texel_significance(uv_area, world_area, len(face_indices)),
        )
        descriptors.append(descriptor)
    
    bm.free()
    return descriptors


def _detect_uv_islands_bmesh(
    bm: bmesh.types.BMesh,
    faces: List[bmesh.types.BMFace],
    uv_layer: bmesh.types.BMLoopUV,
) -> List[Dict[str, Any]]:
    """
    Detect UV islands from a set of faces using connected component analysis.
    
    Uses edge connectivity in UV space to group faces into islands.
    """
    if not faces:
        return []
    
    # Build adjacency based on shared UV edges
    face_set = set(faces)
    face_to_idx = {f: i for i, f in enumerate(faces)}
    
    # Union-Find for island grouping
    parent = list(range(len(faces)))
    
    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    
    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py
    
    # UV coordinate tolerance for matching
    UV_EPSILON = 1e-5
    
    # Build UV edge map: UV coord pair -> face indices
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
            
            # Normalize edge direction for consistent hashing
            edge_key = tuple(sorted([key1, key2]))
            
            if edge_key not in uv_edge_map:
                uv_edge_map[edge_key] = []
            uv_edge_map[edge_key].append(face_idx)
    
    # Union faces that share UV edges
    for edge_key, face_indices in uv_edge_map.items():
        for i in range(1, len(face_indices)):
            union(face_indices[0], face_indices[i])
    
    # Group faces by island
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
            
            # Calculate UV area using shoelace formula
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


def build_material_descriptors(
    meshes: List[bpy.types.Object],
    atlas_resolution: int = 4096,
    build_islands: bool = True,
) -> Dict[str, MaterialDescriptor]:
    """
    Build material descriptors for all materials used by meshes.
    
    Args:
        meshes: List of mesh objects to analyze
        atlas_resolution: Target atlas resolution for stratum calculation
        build_islands: Whether to detect and include UV islands
        
    Returns:
        Dict mapping material_name -> MaterialDescriptor
    """
    descriptors: Dict[str, MaterialDescriptor] = {}
    
    # Collect materials and their usage
    material_meshes: Dict[str, List[str]] = {}  # material_name -> mesh names
    material_stats: Dict[str, Dict[str, float]] = {}  # material_name -> stats
    
    for mesh in meshes:
        if mesh.type != "MESH":
            continue
        
        for mat_slot in mesh.material_slots:
            if not mat_slot.material:
                continue
            
            mat_name = mat_slot.material.name
            
            if mat_name not in material_meshes:
                material_meshes[mat_name] = []
                material_stats[mat_name] = {
                    "uv_area": 0.0,
                    "world_area": 0.0,
                    "face_count": 0,
                }
            
            if mesh.name not in material_meshes[mat_name]:
                material_meshes[mat_name].append(mesh.name)
            
            # Accumulate stats
            stats = _calculate_material_stats(mesh, mat_name)
            material_stats[mat_name]["uv_area"] += stats["uv_area"]
            material_stats[mat_name]["world_area"] += stats["world_area"]
            material_stats[mat_name]["face_count"] += stats["face_count"]
    
    # Build descriptors
    for mat_name, mesh_names in material_meshes.items():
        stats = material_stats[mat_name]
        
        recommended = calculate_recommended_stratum(
            stats["uv_area"],
            stats["world_area"],
            atlas_resolution,
        )
        
        significance = calculate_texel_significance(
            stats["uv_area"],
            stats["world_area"],
            stats["face_count"],
        )
        
        # Build islands if requested
        islands = []
        if build_islands:
            for mesh_name in mesh_names:
                mesh = bpy.data.objects.get(mesh_name)
                if mesh:
                    islands.extend(build_island_descriptors(mesh, mat_name))
        
        descriptor = MaterialDescriptor(
            material_name=mat_name,
            source_mesh_names=mesh_names.copy(),
            stratum=recommended,
            tile_x=0,
            tile_y=0,
            islands=islands,
            total_uv_area=stats["uv_area"],
            total_world_area=stats["world_area"],
            total_face_count=stats["face_count"],
            recommended_stratum=recommended,
            significance=significance,
        )
        
        descriptors[mat_name] = descriptor
    
    return descriptors


def _calculate_material_stats(
    mesh: bpy.types.Object,
    material_name: str,
) -> Dict[str, float]:
    """Calculate UV and world area stats for a material on a mesh."""
    stats = {"uv_area": 0.0, "world_area": 0.0, "face_count": 0}
    
    if mesh.type != "MESH":
        return stats
    
    material = bpy.data.materials.get(material_name)
    if not material:
        return stats
    
    # Find material index
    mat_index = -1
    for idx, mat_slot in enumerate(mesh.material_slots):
        if mat_slot.material == material:
            mat_index = idx
            break
    
    if mat_index < 0:
        return stats
    
    # Get UV layer
    if not mesh.data.uv_layers:
        return stats
    uv_layer = mesh.data.uv_layers[0]
    
    # Calculate areas
    for poly in mesh.data.polygons:
        if poly.material_index != mat_index:
            continue
        
        stats["face_count"] += 1
        stats["world_area"] += poly.area
        
        # Calculate UV area
        uvs = [uv_layer.data[loop_idx].uv for loop_idx in poly.loop_indices]
        n = len(uvs)
        uv_area = 0.0
        for i in range(n):
            j = (i + 1) % n
            uv_area += uvs[i][0] * uvs[j][1]
            uv_area -= uvs[j][0] * uvs[i][1]
        stats["uv_area"] += abs(uv_area) / 2.0
    
    return stats


def build_atlas_descriptor(
    meshes: List[bpy.types.Object],
    atlas_width: int = 4096,
    atlas_height: int = 4096,
    asset_name: str = "",
    auto_place: bool = False,
) -> AtlasDescriptor:
    """
    Build a complete atlas descriptor from meshes.
    
    Args:
        meshes: List of mesh objects
        atlas_width: Target atlas width
        atlas_height: Target atlas height
        asset_name: Name of the parent asset
        auto_place: Whether to auto-place materials in the grid
        
    Returns:
        Complete AtlasDescriptor
    """
    atlas = AtlasDescriptor(
        asset_name=asset_name,
        atlas_width=atlas_width,
        atlas_height=atlas_height,
    )
    
    # Build material descriptors
    mat_descriptors = build_material_descriptors(
        meshes,
        atlas_resolution=max(atlas_width, atlas_height),
    )
    
    # Add materials to atlas
    for mat_name, descriptor in mat_descriptors.items():
        if auto_place:
            # Find a free tile at the recommended stratum
            free_tile = atlas.find_free_tile_for_stratum(descriptor.recommended_stratum)
            if free_tile:
                descriptor.tile_x, descriptor.tile_y = free_tile
                descriptor.stratum = descriptor.recommended_stratum
            else:
                # Try lower stratums
                for s in range(descriptor.recommended_stratum + 1, atlas.max_stratum + 1):
                    free_tile = atlas.find_free_tile_for_stratum(s)
                    if free_tile:
                        descriptor.tile_x, descriptor.tile_y = free_tile
                        descriptor.stratum = s
                        break
        
        atlas.add_material(descriptor)
    
    return atlas
