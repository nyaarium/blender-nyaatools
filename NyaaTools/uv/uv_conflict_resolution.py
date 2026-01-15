"""
UV conflict resolution for pre-merge standardization.

Detects and resolves UV name conflicts when merging meshes with different
first UV layer names. Preserves all extra UV layers and renames the first
UV layer to "UVMap" to resolve naming conflicts.
"""

import bpy
from typing import Dict, List, Optional, Callable


def detect_uv_conflicts(meshes: List[bpy.types.Object]) -> bool:
    """
    Detect if there are UV name conflicts among meshes.

    Args:
        meshes: List of mesh objects to check

    Returns:
        True if UV conflicts exist (different first UV layer names), False otherwise
    """
    if not meshes or len(meshes) < 2:
        return False

    # Get first UV layer name from each mesh
    first_uv_names = set()
    for mesh in meshes:
        if mesh.type != "MESH":
            continue
        if not mesh.data.uv_layers:
            continue
        first_uv = mesh.data.uv_layers[0].name
        first_uv_names.add(first_uv)

    return len(first_uv_names) > 1


def check_uv_map_conflicts(meshes: List[bpy.types.Object]) -> bool:
    """
    Check if any mesh has "UVMap" in a non-first slot (which would cause merge issues).

    Args:
        meshes: List of mesh objects to check

    Returns:
        True if conflicts exist, False otherwise
    """
    for mesh in meshes:
        if mesh.type != "MESH":
            continue
        for idx, uv_layer in enumerate(mesh.data.uv_layers):
            if uv_layer.name == "UVMap" and idx != 0:
                return True
    return False


def standardize_uvs_for_merge(
    meshes: List[bpy.types.Object],
    debug_print: Optional[Callable[..., None]] = None,
) -> None:
    """
    Rename first UV layer to "UVMap" for all meshes.

    Preserves all extra UV layers. Only the first UV layer name is changed.

    Args:
        meshes: List of mesh objects to standardize
        debug_print: Optional debug print function
    """
    if debug_print is None:

        def debug_print(*args):
            pass

    debug_print("  Standardizing UVs for merge...")

    for mesh in meshes:
        if mesh.type != "MESH":
            continue

        if not mesh.data.uv_layers:
            debug_print(f"    ⚠️ {mesh.name} has no UV layers")
            continue

        # Rename first UV to "UVMap"
        first_uv = mesh.data.uv_layers[0]
        if first_uv.name != "UVMap":
            old_name = first_uv.name
            first_uv.name = "UVMap"
            debug_print(f"    Renamed '{old_name}' → 'UVMap' on {mesh.name}")

    debug_print("  ✅ UV standardization complete")


def resolve_layer_uv_conflicts(
    layer_name: str,
    layer_meshes: Dict[str, bpy.types.Object],
    debug_print: Optional[Callable[..., None]] = None,
) -> None:
    """
    Resolve UV name conflicts for meshes in a layer.

    Checks for conflicting first UV names and standardizes them by renaming
    the first UV to "UVMap".

    Args:
        layer_name: Name of the layer
        layer_meshes: Dict of {mesh_name: mesh_object} for this layer
        debug_print: Optional debug print function
    """
    if debug_print is None:

        def debug_print(*args):
            pass

    meshes = list(layer_meshes.values())
    if len(meshes) < 2:
        return

    # Check for UVMap slot conflicts first
    if check_uv_map_conflicts(meshes):
        raise Exception(
            f"Layer '{layer_name}' has meshes with 'UVMap' in non-first slot. "
            f"Please reorder UV layers so 'UVMap' is in the first slot."
        )

    # Detect UV name conflicts
    has_conflicts = detect_uv_conflicts(meshes)

    if has_conflicts:
        debug_print(f"🔧 UV conflicts detected in layer '{layer_name}'")
        debug_print(f"   Applying pre-merge UV standardization...")

        # Standardize UVs to resolve conflicts
        # Preserves all extra UV layers - only renames first UV to "UVMap"
        standardize_uvs_for_merge(meshes, debug_print)

        debug_print(f"   ✅ Layer '{layer_name}' ready for merge")
