"""
Stratum mathematics and grid calculations.

Provides utilities for working with the stratum hierarchy:
- Grid size calculations (power-of-2 for now, designed for flexibility)
- UV scale and offset computations
- Tile position validation and bounds

The stratum system uses a mipmap-like hierarchy where:
- Stratum 0 = Full resolution (1x1 grid)
- Stratum N = 2^N × 2^N grid with 1/2^N scale per tile
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, List, Optional
import math


# -----------------------------------------------------------------------------
# Core Stratum Calculations
# -----------------------------------------------------------------------------


def stratum_to_grid_size(stratum: int) -> int:
    """
    Get the grid size for a stratum level.
    
    Currently power-of-2 only:
    - Stratum 0 → 1x1
    - Stratum 1 → 2x2
    - Stratum 2 → 4x4
    - Stratum n → 2^n × 2^n
    
    Args:
        stratum: The stratum level (0+)
        
    Returns:
        Grid dimension (same for x and y)
    """
    if stratum < 0:
        raise ValueError(f"Stratum must be non-negative, got {stratum}")
    return 2 ** stratum


def stratum_to_scale(stratum: int) -> float:
    """
    Get the UV scale factor for a stratum level.
    
    Args:
        stratum: The stratum level (0+)
        
    Returns:
        Scale factor (1.0 for stratum 0, 0.5 for stratum 1, etc.)
    """
    if stratum < 0:
        raise ValueError(f"Stratum must be non-negative, got {stratum}")
    return 1.0 / (2 ** stratum)


def tile_to_uv_offset(stratum: int, tile_x: int, tile_y: int) -> Tuple[float, float]:
    """
    Calculate UV offset for a tile position within a stratum.
    
    Args:
        stratum: The stratum level
        tile_x: X position in grid (0 to grid_size-1)
        tile_y: Y position in grid (0 to grid_size-1)
        
    Returns:
        (u_offset, v_offset) tuple
    """
    scale = stratum_to_scale(stratum)
    return (tile_x * scale, tile_y * scale)


def get_tile_bounds(
    stratum: int, 
    tile_x: int, 
    tile_y: int
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """
    Get the UV bounds for a tile.
    
    Args:
        stratum: The stratum level
        tile_x: X position in grid
        tile_y: Y position in grid
        
    Returns:
        ((u_min, v_min), (u_max, v_max)) bounds tuple
    """
    scale = stratum_to_scale(stratum)
    u_min = tile_x * scale
    v_min = tile_y * scale
    return ((u_min, v_min), (u_min + scale, v_min + scale))


def validate_tile_position(stratum: int, tile_x: int, tile_y: int) -> bool:
    """
    Check if a tile position is valid for a stratum.
    
    Args:
        stratum: The stratum level
        tile_x: X position in grid
        tile_y: Y position in grid
        
    Returns:
        True if valid, False otherwise
    """
    grid_size = stratum_to_grid_size(stratum)
    return 0 <= tile_x < grid_size and 0 <= tile_y < grid_size


def stratum_max_tiles(stratum: int) -> int:
    """
    Get the total number of tiles available in a stratum.
    
    Args:
        stratum: The stratum level
        
    Returns:
        Total tile count (4^stratum)
    """
    grid_size = stratum_to_grid_size(stratum)
    return grid_size * grid_size


def tile_index_to_coords(stratum: int, tile_index: int) -> Tuple[int, int]:
    """
    Convert a linear tile index to (x, y) coordinates.
    
    Args:
        stratum: The stratum level
        tile_index: Linear index (0 to 4^stratum - 1)
        
    Returns:
        (tile_x, tile_y) tuple
    """
    grid_size = stratum_to_grid_size(stratum)
    if tile_index < 0 or tile_index >= grid_size * grid_size:
        raise ValueError(f"Tile index {tile_index} out of range for stratum {stratum}")
    return (tile_index % grid_size, tile_index // grid_size)


def tile_coords_to_index(stratum: int, tile_x: int, tile_y: int) -> int:
    """
    Convert (x, y) coordinates to a linear tile index.
    
    Args:
        stratum: The stratum level
        tile_x: X position in grid
        tile_y: Y position in grid
        
    Returns:
        Linear tile index
    """
    if not validate_tile_position(stratum, tile_x, tile_y):
        raise ValueError(f"Invalid tile position ({tile_x}, {tile_y}) for stratum {stratum}")
    grid_size = stratum_to_grid_size(stratum)
    return tile_y * grid_size + tile_x


# -----------------------------------------------------------------------------
# Stratum Promotion/Demotion
# -----------------------------------------------------------------------------


def promote_tile_coords(
    current_stratum: int, 
    tile_x: int, 
    tile_y: int
) -> Tuple[int, int, int]:
    """
    Calculate new tile coordinates when promoting to a higher-resolution stratum.
    
    Promoting means moving from stratum N to stratum N-1 (larger tiles).
    The tile will occupy the same relative position but in a coarser grid.
    
    Args:
        current_stratum: Current stratum level
        tile_x: Current X position
        tile_y: Current Y position
        
    Returns:
        (new_stratum, new_tile_x, new_tile_y)
        
    Raises:
        ValueError: If already at stratum 0 (cannot promote further)
    """
    if current_stratum <= 0:
        raise ValueError("Cannot promote beyond stratum 0")
    
    new_stratum = current_stratum - 1
    # When promoting, coordinates scale up (tile covers more UV space)
    # The tile at (2, 3) in stratum 2 becomes (1, 1) in stratum 1
    new_tile_x = tile_x // 2
    new_tile_y = tile_y // 2
    
    return (new_stratum, new_tile_x, new_tile_y)


def demote_tile_coords(
    current_stratum: int, 
    tile_x: int, 
    tile_y: int,
    max_stratum: int = 8,
) -> Tuple[int, int, int]:
    """
    Calculate new tile coordinates when demoting to a lower-resolution stratum.
    
    Demoting means moving from stratum N to stratum N+1 (smaller tiles).
    The tile will occupy the top-left quadrant of its previous position.
    
    Args:
        current_stratum: Current stratum level
        tile_x: Current X position
        tile_y: Current Y position
        max_stratum: Maximum allowed stratum level
        
    Returns:
        (new_stratum, new_tile_x, new_tile_y)
        
    Raises:
        ValueError: If at or beyond max_stratum
    """
    if current_stratum >= max_stratum:
        raise ValueError(f"Cannot demote beyond stratum {max_stratum}")
    
    new_stratum = current_stratum + 1
    # When demoting, coordinates scale down (tile covers less UV space)
    # The tile at (1, 1) in stratum 1 becomes (2, 2) in stratum 2
    new_tile_x = tile_x * 2
    new_tile_y = tile_y * 2
    
    return (new_stratum, new_tile_x, new_tile_y)


# -----------------------------------------------------------------------------
# StratumGrid Class
# -----------------------------------------------------------------------------


@dataclass
class StratumGrid:
    """
    Represents the atlas grid configuration.
    
    Tracks which tiles are occupied at each stratum level and provides
    utilities for finding free tiles and validating placements.
    
    Attributes:
        max_stratum: Maximum stratum depth allowed
        occupied: Dict mapping stratum -> set of (tile_x, tile_y) tuples
    """
    
    max_stratum: int = 8
    occupied: dict = field(default_factory=dict)
    
    def __post_init__(self):
        # Initialize occupied sets for each stratum
        if not self.occupied:
            self.occupied = {s: set() for s in range(self.max_stratum + 1)}
    
    def is_tile_free(self, stratum: int, tile_x: int, tile_y: int) -> bool:
        """Check if a specific tile is free (not occupied or overlapping)."""
        if not validate_tile_position(stratum, tile_x, tile_y):
            return False
        
        # Check this tile
        if (tile_x, tile_y) in self.occupied.get(stratum, set()):
            return False
        
        # Check parent tiles (coarser stratums that would overlap)
        for s in range(stratum):
            scale_factor = 2 ** (stratum - s)
            parent_x = tile_x // scale_factor
            parent_y = tile_y // scale_factor
            if (parent_x, parent_y) in self.occupied.get(s, set()):
                return False
        
        # Check child tiles (finer stratums that would overlap)
        for s in range(stratum + 1, self.max_stratum + 1):
            scale_factor = 2 ** (s - stratum)
            child_x_start = tile_x * scale_factor
            child_y_start = tile_y * scale_factor
            child_occupied = self.occupied.get(s, set())
            
            for cx in range(child_x_start, child_x_start + scale_factor):
                for cy in range(child_y_start, child_y_start + scale_factor):
                    if (cx, cy) in child_occupied:
                        return False
        
        return True
    
    def occupy_tile(self, stratum: int, tile_x: int, tile_y: int) -> bool:
        """
        Mark a tile as occupied.
        
        Returns:
            True if successful, False if tile is not free
        """
        if not self.is_tile_free(stratum, tile_x, tile_y):
            return False
        
        if stratum not in self.occupied:
            self.occupied[stratum] = set()
        
        self.occupied[stratum].add((tile_x, tile_y))
        return True
    
    def release_tile(self, stratum: int, tile_x: int, tile_y: int) -> bool:
        """
        Mark a tile as free.
        
        Returns:
            True if tile was occupied and is now free, False if wasn't occupied
        """
        if stratum not in self.occupied:
            return False
        
        if (tile_x, tile_y) not in self.occupied[stratum]:
            return False
        
        self.occupied[stratum].remove((tile_x, tile_y))
        return True
    
    def find_free_tile(self, stratum: int) -> Optional[Tuple[int, int]]:
        """
        Find the first free tile at a given stratum.
        
        Args:
            stratum: The stratum level to search
            
        Returns:
            (tile_x, tile_y) of first free tile, or None if stratum is full
        """
        grid_size = stratum_to_grid_size(stratum)
        
        for ty in range(grid_size):
            for tx in range(grid_size):
                if self.is_tile_free(stratum, tx, ty):
                    return (tx, ty)
        
        return None
    
    def get_all_free_tiles(self, stratum: int) -> List[Tuple[int, int]]:
        """Get all free tiles at a given stratum."""
        grid_size = stratum_to_grid_size(stratum)
        free_tiles = []
        
        for ty in range(grid_size):
            for tx in range(grid_size):
                if self.is_tile_free(stratum, tx, ty):
                    free_tiles.append((tx, ty))
        
        return free_tiles
    
    def calculate_coverage(self) -> float:
        """
        Calculate what fraction of the atlas is covered.
        
        Returns:
            Coverage ratio (0.0 to 1.0)
        """
        total_coverage = 0.0
        
        for stratum, tiles in self.occupied.items():
            tile_area = stratum_to_scale(stratum) ** 2
            total_coverage += len(tiles) * tile_area
        
        return min(total_coverage, 1.0)
    
    def clear(self):
        """Clear all occupied tiles."""
        self.occupied = {s: set() for s in range(self.max_stratum + 1)}


# -----------------------------------------------------------------------------
# Texel Density Calculations
# -----------------------------------------------------------------------------


def calculate_recommended_stratum(
    uv_area: float,
    world_area: float,
    atlas_resolution: int,
    target_texel_density: Optional[float] = None,
) -> int:
    """
    Calculate the recommended stratum for a material based on texel density.
    
    Uses the ratio of UV space area to world space area to determine
    appropriate resolution allocation in the atlas.
    
    Args:
        uv_area: Total UV space area (0.0 to 1.0 normalized)
        world_area: Total world space surface area
        atlas_resolution: Target atlas resolution (e.g., 4096)
        target_texel_density: Optional target pixels per world unit
        
    Returns:
        Recommended stratum level (0 = full res, higher = smaller)
    """
    if uv_area <= 0 or world_area <= 0:
        return 4  # Default to small for invalid inputs
    
    # Calculate current texel density
    # Higher UV area relative to world area = higher density needed
    density_ratio = uv_area / world_area
    
    # Normalize to atlas resolution
    effective_pixels = atlas_resolution * atlas_resolution * uv_area
    
    # Determine stratum based on pixel budget
    # Stratum 0: full atlas (all pixels)
    # Stratum 1: 1/4 of atlas (quarter pixels per material)
    # Stratum 2: 1/16 of atlas
    # etc.
    
    # Simple heuristic: if UV area is small, use higher stratum
    if uv_area > 0.5:
        return 0
    elif uv_area > 0.2:
        return 1
    elif uv_area > 0.05:
        return 2
    elif uv_area > 0.01:
        return 3
    else:
        return 4


def calculate_texel_significance(
    uv_area: float,
    world_area: float,
    face_count: int,
) -> float:
    """
    Calculate a significance score for texel density prioritization.
    
    Higher scores indicate materials that should get more atlas space.
    
    Args:
        uv_area: UV space area
        world_area: World space surface area
        face_count: Number of faces using this material
        
    Returns:
        Significance score (0.0 to 1.0)
    """
    if uv_area <= 0 or world_area <= 0 or face_count <= 0:
        return 0.0
    
    # Combine factors:
    # - Larger world area = more visible = higher priority
    # - More faces = more important = higher priority
    # - Higher UV density ratio = needs more pixels
    
    density_ratio = uv_area / world_area
    
    # Normalize with soft caps
    world_factor = min(world_area / 10.0, 1.0)  # Cap at 10 square units
    face_factor = min(face_count / 1000.0, 1.0)  # Cap at 1000 faces
    density_factor = min(density_ratio * 10.0, 1.0)  # Scale density
    
    # Weighted combination
    significance = (
        world_factor * 0.4 +
        face_factor * 0.3 +
        density_factor * 0.3
    )
    
    return min(max(significance, 0.0), 1.0)
