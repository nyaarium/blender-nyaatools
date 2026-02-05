"""
Capture baking for atlas materials.

Handles per-material intermediate baking before atlas recombination.
Each material is baked to its own set of textures using the original UVs,
then stored in the MaterialDescriptor for later recombination.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Callable, Tuple, Any
import bpy

from .descriptors import MaterialDescriptor, AtlasDescriptor


def capture_material_bakes(
    atlas: AtlasDescriptor,
    bake_formats: List[str],
    resolution: Optional[Tuple[int, int]] = None,
    debug_print: Optional[Callable[..., None]] = None,
) -> Dict[str, Dict[str, bpy.types.Image]]:
    """
    Capture bakes for all materials in an atlas.
    
    Bakes each material to intermediate textures using original UVs.
    Results are stored in each MaterialDescriptor's captured_images dict.
    
    Args:
        atlas: The atlas descriptor containing materials
        bake_formats: List of DTP format strings to bake (e.g., ["rgba", "normalgl"])
        resolution: Optional fixed resolution (width, height). If None, uses atlas resolution.
        debug_print: Optional debug print function
        
    Returns:
        Dict mapping material_name -> {format: image}
    """
    if debug_print is None:
        def debug_print(*args):
            pass
    
    if resolution is None:
        resolution = (atlas.atlas_width, atlas.atlas_height)
    
    results: Dict[str, Dict[str, bpy.types.Image]] = {}
    
    debug_print(f"Capturing bakes for {len(atlas.materials)} materials...")
    
    for mat_name, descriptor in atlas.materials.items():
        debug_print(f"  Capturing {mat_name}...")
        
        captured = capture_single_material(
            descriptor,
            bake_formats,
            resolution,
            debug_print,
        )
        
        results[mat_name] = captured
    
    debug_print(f"✅ Captured {len(results)} materials")
    return results


def capture_single_material(
    descriptor: MaterialDescriptor,
    bake_formats: List[str],
    resolution: Tuple[int, int],
    debug_print: Optional[Callable[..., None]] = None,
) -> Dict[str, bpy.types.Image]:
    """
    Capture bakes for a single material.
    
    Bakes the material using its ORIGINAL UVs. The captured image will contain
    the texture data at the original UV positions. During recombination, the
    shader will sample these images using the original UVMap while writing
    to the atlas UV positions.
    
    Args:
        descriptor: The MaterialDescriptor to bake
        bake_formats: List of DTP format strings to bake
        resolution: Resolution (width, height) for baked images
        debug_print: Optional debug print function
        
    Returns:
        Dict mapping format -> baked image
    """
    if debug_print is None:
        def debug_print(*args):
            pass
    
    from ..image.texture_baker import bake_dtp_texture
    
    material = descriptor.get_material()
    if not material:
        debug_print(f"    ⚠️ Material '{descriptor.material_name}' not found")
        return {}
    
    meshes = descriptor.get_source_meshes()
    if not meshes:
        debug_print(f"    ⚠️ No meshes found for '{descriptor.material_name}'")
        return {}
    
    captured: Dict[str, bpy.types.Image] = {}
    
    # For multi-mesh materials, bake from first mesh
    mesh = meshes[0]
    
    # Use first UV layer (original UVs) for capture
    uv_name = None
    if mesh.data.uv_layers:
        uv_name = mesh.data.uv_layers[0].name
    
    if not uv_name:
        debug_print(f"    ⚠️ No UV layer found on mesh '{mesh.name}'")
        return {}
    
    # Count faces for this material
    mat_index = -1
    for idx, mat_slot in enumerate(mesh.material_slots):
        if mat_slot.material == material:
            mat_index = idx
            break
    
    debug_print(f"      Using original UV layer: {uv_name}")
    
    for dtp_format in bake_formats:
        debug_print(f"    Baking {dtp_format}...")
        
        result_image = bake_dtp_texture(
            dtp_format=dtp_format,
            obj=mesh,
            material=material,
            resolution=resolution,
            max_resolution=resolution,
            uv_layer_name=uv_name,
            image_type="png",
        )
        
        if result_image:
            captured[dtp_format] = result_image
            descriptor.captured_images[dtp_format] = result_image
            debug_print(f"      ✅ Captured {dtp_format}")
        else:
            debug_print(f"      ⚠️ Failed to capture {dtp_format}")
    
    return captured


def capture_multi_mesh_material(
    descriptor: MaterialDescriptor,
    bake_formats: List[str],
    resolution: Tuple[int, int],
    debug_print: Optional[Callable[..., None]] = None,
) -> Dict[str, Dict[str, bpy.types.Image]]:
    """
    Capture bakes for a material used by multiple meshes.
    
    Each mesh is baked separately, returning a dict of mesh_name -> {format: image}.
    This is used when materials span multiple meshes that haven't been merged yet.
    
    Args:
        descriptor: The MaterialDescriptor to bake
        bake_formats: List of DTP format strings to bake
        resolution: Resolution (width, height) for baked images
        debug_print: Optional debug print function
        
    Returns:
        Dict mapping mesh_name -> {format: image}
    """
    if debug_print is None:
        def debug_print(*args):
            pass
    
    from ..image.texture_baker import bake_dtp_texture
    
    material = descriptor.get_material()
    if not material:
        debug_print(f"    ⚠️ Material '{descriptor.material_name}' not found")
        return {}
    
    meshes = descriptor.get_source_meshes()
    if not meshes:
        debug_print(f"    ⚠️ No meshes found for '{descriptor.material_name}'")
        return {}
    
    results: Dict[str, Dict[str, bpy.types.Image]] = {}
    
    for mesh in meshes:
        mesh_name = mesh.name
        debug_print(f"    Capturing mesh '{mesh_name}'...")
        
        results[mesh_name] = {}
        
        # Get first UV layer name
        uv_name = None
        if mesh.data.uv_layers:
            uv_name = mesh.data.uv_layers[0].name
        
        for dtp_format in bake_formats:
            result_image = bake_dtp_texture(
                dtp_format=dtp_format,
                obj=mesh,
                material=material,
                resolution=resolution,
                max_resolution=resolution,
                uv_layer_name=uv_name,
                image_type="png",
            )
            
            if result_image:
                results[mesh_name][dtp_format] = result_image
                debug_print(f"      ✅ {mesh_name}/{dtp_format}")
            else:
                debug_print(f"      ⚠️ Failed {mesh_name}/{dtp_format}")
    
    return results


def get_consolidated_bake_formats(requested_formats: List[str]) -> List[str]:
    """
    Consolidate requested DTP formats into intermediate bake formats.
    
    Maps complex formats to standard intermediate formats:
    - Color formats (rgba, rgb, cr, cg, cb, etc.) -> "rgba"
    - Normal formats (normalgl, normaldx, nx, ng, nd) -> "normalgl"
    - PBR formats (me, ro, sp, ao) -> "me-ro-sp"
    - Emission formats -> "emission"
    
    Args:
        requested_formats: List of requested DTP format strings
        
    Returns:
        List of consolidated intermediate format strings
    """
    targets = set()
    
    dtp_category_map = {
        "rgba": ["cr", "cg", "cb", "al", "lr", "lg", "lb", "rgba", "rgb"],
        "normalgl": ["nx", "nd", "ng", "normaldx", "normalgl"],
        "me-ro-sp": ["me", "ro", "sp", "ao", "sm"],
        "emission": ["er", "eg", "eb", "es", "emission"],
    }
    
    for fmt in requested_formats:
        fmt_lower = fmt.lower()
        
        for target, keywords in dtp_category_map.items():
            if target in targets:
                continue
            
            # Check direct match
            if fmt_lower == target:
                targets.add(target)
                continue
            
            # Check channel keywords
            channels = fmt_lower.split("-")
            for kw in keywords:
                if kw in channels or fmt_lower == kw:
                    targets.add(target)
                    break
    
    return list(targets)


def cleanup_captured_images(
    atlas: AtlasDescriptor,
    debug_print: Optional[Callable[..., None]] = None,
) -> int:
    """
    Clean up all captured intermediate images from Blender.
    
    Args:
        atlas: The atlas descriptor
        debug_print: Optional debug print function
        
    Returns:
        Number of images removed
    """
    if debug_print is None:
        def debug_print(*args):
            pass
    
    count = 0
    
    for mat_name, descriptor in atlas.materials.items():
        for format_name, image in list(descriptor.captured_images.items()):
            if image and image.name in bpy.data.images:
                bpy.data.images.remove(image)
                count += 1
        descriptor.captured_images.clear()
    
    debug_print(f"Cleaned up {count} intermediate images")
    return count
