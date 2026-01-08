"""
Bake context management.

Handles the state and configuration for baking operations.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any
import bpy


@dataclass
class MeshMeta:
    """
    Metadata for a mesh in the baking pipeline.

    Tracks the mesh object and its properties without using fragile name checks.
    """

    mesh_object: bpy.types.Object
    layer_name: str
    is_ue_collider: bool
    original_name: str = ""

    def __post_init__(self):
        if not self.original_name:
            self.original_name = self.mesh_object.name


@dataclass
class BakeImageConfig:
    """Configuration for a single bake output."""

    format: str  # DTP format string (e.g., "rgba", "normalgl", "me-sp-ro")
    image_type: str  # "png" or "exr"
    width: int
    height: int
    optimize_resolution: bool = True


@dataclass
class BakeContext:
    """
    Complete context for a baking operation.

    Tracks all state needed for the multi-mesh baking pipeline:
    - Source meshes and their metadata (using is_ue_collider flag, not UCX_ naming)
    - Bake configurations
    - Output paths
    - Cleanup callbacks
    """

    # Mesh tracking by metadata (no UCX_ name checks)
    mesh_metas: List[MeshMeta] = field(default_factory=list)

    # Meshes grouped by material (built during prepare phase)
    meshes_by_material: Dict[str, List[bpy.types.Object]] = field(default_factory=dict)

    # Bake configurations
    bake_images: List[BakeImageConfig] = field(default_factory=list)

    # Output configuration
    export_dir: str = ""
    filename_formatter: Optional[Callable[[str, str, str], str]] = None

    # Flags
    save_to_file: bool = True
    wait_for_enter: bool = True  # Merge & Export sets this to False

    # Cleanup - called with reason: 'success' | 'error' | 'cancel'
    on_cleanup: Optional[Callable[[str], None]] = None

    # Debug state
    debug_mode: bool = False

    def get_non_collider_meshes(self) -> List[bpy.types.Object]:
        """Get all non-collider mesh objects."""
        return [m.mesh_object for m in self.mesh_metas if not m.is_ue_collider]

    def get_collider_meshes(self) -> List[bpy.types.Object]:
        """Get all collider mesh objects."""
        return [m.mesh_object for m in self.mesh_metas if m.is_ue_collider]

    def debug_print(self, *msgs):
        """Print debug messages if debug mode is enabled."""
        if self.debug_mode:
            print("   ", *msgs)


# =============================================================================
# Global Pending Context
# =============================================================================

_pending_bake_context: Optional[BakeContext] = None


def set_pending_bake_context(
    meshes: List[bpy.types.Object],
    bake_images: List[Any],
    export_dir: str,
    on_cleanup: Optional[Callable[[], None]] = None,
    filename_formatter: Optional[Callable[[str, str, str], str]] = None,
    wait_for_enter: bool = True,
    asset_host: Optional[bpy.types.Object] = None,
) -> BakeContext:
    """
    Set up a bake context for the modal bake operator.

    Args:
        meshes: List of mesh objects to bake from
        bake_images: List of bake image configs (dicts or PropertyGroups)
        export_dir: Directory to save baked textures
        on_cleanup: Optional callback when baking finishes
        filename_formatter: Optional custom filename formatter
        wait_for_enter: If True, wait for user confirmation before each bake
        asset_host: Optional asset host for reading mesh metadata (is_ue_collider)

    Returns:
        The created BakeContext
    """
    global _pending_bake_context

    # Build mesh metas using is_ue_collider and layer_name from asset config
    mesh_metas = []
    collider_set = set()
    layer_name_map = {}  # mesh_name -> layer_name

    # If we have an asset host, extract metadata from config
    if asset_host and hasattr(asset_host, "nyaa_asset"):
        cfg = asset_host.nyaa_asset
        for entry in cfg.meshes:
            if entry.mesh_object:
                if entry.is_ue_collider:
                    collider_set.add(entry.mesh_object.name)
                if entry.layer_name:
                    layer_name_map[entry.mesh_object.name] = entry.layer_name

    for mesh in meshes:
        is_collider = mesh.name in collider_set
        layer_name = layer_name_map.get(mesh.name, "")  # Use from config if available
        meta = MeshMeta(
            mesh_object=mesh,
            layer_name=layer_name,
            is_ue_collider=is_collider,
        )
        mesh_metas.append(meta)

    # Convert bake image configs
    bake_configs = []
    for img in bake_images:
        if isinstance(img, dict):
            bake_configs.append(
                BakeImageConfig(
                    format=img["format"],
                    image_type=img["image_type"],
                    width=int(img["width"]),
                    height=int(img["height"]),
                    optimize_resolution=img.get("optimize_resolution", True),
                )
            )
        else:
            # PropertyGroup access
            bake_configs.append(
                BakeImageConfig(
                    format=img.format,
                    image_type=img.image_type,
                    width=int(img.width),
                    height=int(img.height),
                    optimize_resolution=img.optimize_resolution,
                )
            )

    ctx = BakeContext(
        mesh_metas=mesh_metas,
        bake_images=bake_configs,
        export_dir=export_dir,
        on_cleanup=on_cleanup,
        filename_formatter=filename_formatter,
        wait_for_enter=wait_for_enter,
    )

    _pending_bake_context = ctx
    return ctx


def get_pending_bake_context() -> Optional[BakeContext]:
    """Get and clear the pending bake context."""
    global _pending_bake_context
    ctx = _pending_bake_context
    _pending_bake_context = None
    return ctx


def clear_pending_bake_context():
    """Clear any pending bake context without using it."""
    global _pending_bake_context
    _pending_bake_context = None


def has_pending_bake_context() -> bool:
    """Check if there's a pending bake context."""
    return _pending_bake_context is not None
