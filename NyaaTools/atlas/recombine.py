"""
Atlas recombination - final merge and bake.

Handles the final steps of atlas creation:
1. Apply atlas UV transforms to meshes
2. Merge meshes with face attribute tagging
3. Build recombination shader (Mix Shader chain)
4. Execute final bake to atlas texture
"""

from __future__ import annotations
from typing import Dict, List, Optional, Callable, Tuple, Any
import bpy
import random

from .descriptors import MaterialDescriptor, AtlasDescriptor
from .stratum import tile_to_uv_offset, stratum_to_scale


# UV layer name for atlas (-- prefix means deleted on export)
ATLAS_UV_NAME = "-- Atlas"


# -----------------------------------------------------------------------------
# UV Transform Functions
# -----------------------------------------------------------------------------


def create_atlas_uv_layer(mesh: bpy.types.Object) -> Optional[bpy.types.MeshUVLoopLayer]:
    """
    Create or get the atlas UV layer on a mesh.
    
    The atlas UV layer uses the "--" prefix, meaning it will be
    automatically deleted during export.
    
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


def copy_uvs_to_atlas_layer(
    mesh: bpy.types.Object,
    source_uv_name: str = "UVMap",
) -> bool:
    """
    Copy UVs from source layer to atlas layer.
    
    Args:
        mesh: The mesh object
        source_uv_name: Name of source UV layer
        
    Returns:
        True if successful
    """
    if mesh.type != "MESH":
        return False
    
    if source_uv_name not in mesh.data.uv_layers:
        return False
    
    atlas_uv = create_atlas_uv_layer(mesh)
    if not atlas_uv:
        return False
    
    source_uv = mesh.data.uv_layers[source_uv_name]
    
    # Copy all UV coordinates
    for i, loop_data in enumerate(source_uv.data):
        atlas_uv.data[i].uv = loop_data.uv.copy()
    
    return True


def transform_atlas_uvs_for_material(
    mesh: bpy.types.Object,
    material_name: str,
    stratum: int,
    tile_x: int,
    tile_y: int,
    debug_print: Optional[Callable[..., None]] = None,
) -> bool:
    """
    Transform atlas UVs for faces using a specific material.
    
    Applies scale and offset based on stratum placement:
    - new_u = old_u * scale + offset_x
    - new_v = old_v * scale + offset_y
    
    Args:
        mesh: The mesh object
        material_name: Material to transform
        stratum: Stratum level
        tile_x: X position in stratum grid
        tile_y: Y position in stratum grid
        debug_print: Optional debug function
        
    Returns:
        True if successful
    """
    if debug_print is None:
        def debug_print(*args):
            pass
    
    if mesh.type != "MESH":
        return False
    
    # Find material index
    material = bpy.data.materials.get(material_name)
    if not material:
        return False
    
    mat_index = -1
    for idx, mat_slot in enumerate(mesh.material_slots):
        if mat_slot.material == material:
            mat_index = idx
            break
    
    if mat_index < 0:
        return False
    
    # Ensure atlas UV layer exists
    atlas_uv = mesh.data.uv_layers.get(ATLAS_UV_NAME)
    if not atlas_uv:
        return False
    
    # Calculate transform
    scale = stratum_to_scale(stratum)
    offset_x, offset_y = tile_to_uv_offset(stratum, tile_x, tile_y)
    
    # Transform UVs for faces using this material
    face_count = 0
    loop_count = 0
    
    for poly in mesh.data.polygons:
        if poly.material_index != mat_index:
            continue
        
        for loop_idx in poly.loop_indices:
            uv = atlas_uv.data[loop_idx].uv
            atlas_uv.data[loop_idx].uv = (
                uv[0] * scale + offset_x,
                uv[1] * scale + offset_y,
            )
            loop_count += 1
        face_count += 1
    
    debug_print(f"    Transformed {face_count} faces for {material_name}")
    return True


def apply_atlas_transforms(
    atlas: AtlasDescriptor,
    debug_print: Optional[Callable[..., None]] = None,
) -> bool:
    """
    Apply atlas UV transforms to all meshes based on material placements.
    
    Creates "-- Atlas" UV layer on each mesh and transforms coordinates
    based on each material's stratum and tile position.
    
    Args:
        atlas: The atlas descriptor with material placements
        debug_print: Optional debug function
        
    Returns:
        True if successful
    """
    if debug_print is None:
        def debug_print(*args):
            pass
    
    debug_print("Applying atlas transforms...")
    
    # Collect all unique meshes
    all_meshes: Dict[str, bpy.types.Object] = {}
    for mat_name, descriptor in atlas.materials.items():
        for mesh_name in descriptor.source_mesh_names:
            if mesh_name not in all_meshes:
                mesh = bpy.data.objects.get(mesh_name)
                if mesh and mesh.type == "MESH":
                    all_meshes[mesh_name] = mesh
    
    # Create atlas UV layers and copy source UVs
    debug_print(f"  Creating atlas UV layers on {len(all_meshes)} meshes...")
    for mesh_name, mesh in all_meshes.items():
        copy_uvs_to_atlas_layer(mesh, "UVMap")
    
    # Apply transforms per material
    debug_print(f"  Transforming {len(atlas.materials)} materials...")
    for mat_name, descriptor in atlas.materials.items():
        for mesh_name in descriptor.source_mesh_names:
            mesh = all_meshes.get(mesh_name)
            if not mesh:
                continue
            
            transform_atlas_uvs_for_material(
                mesh,
                mat_name,
                descriptor.stratum,
                descriptor.tile_x,
                descriptor.tile_y,
                debug_print,
            )
    
    debug_print("✅ Atlas transforms applied")
    return True


def remove_atlas_uv_layers(
    meshes: List[bpy.types.Object],
    debug_print: Optional[Callable[..., None]] = None,
) -> int:
    """
    Remove atlas UV layers from meshes.
    
    Args:
        meshes: List of mesh objects
        debug_print: Optional debug function
        
    Returns:
        Number of layers removed
    """
    if debug_print is None:
        def debug_print(*args):
            pass
    
    count = 0
    for mesh in meshes:
        if mesh.type != "MESH":
            continue
        
        if ATLAS_UV_NAME in mesh.data.uv_layers:
            mesh.data.uv_layers.remove(mesh.data.uv_layers[ATLAS_UV_NAME])
            count += 1
    
    debug_print(f"Removed {count} atlas UV layers")
    return count


# -----------------------------------------------------------------------------
# Mesh Merging
# -----------------------------------------------------------------------------


def set_face_material_index_attribute(
    mesh: bpy.types.Object,
    material_name: str,
    index: int,
    debug_print: Optional[Callable[..., None]] = None,
) -> int:
    """
    Set a face attribute on faces using a specific material.
    
    The attribute "atlas_mat_index" stores which material originally
    owned each face, used for recombination shader routing.
    
    Args:
        mesh: The mesh object
        material_name: Material to tag
        index: Index value to assign
        debug_print: Optional debug function
        
    Returns:
        Number of faces tagged
    """
    if debug_print is None:
        def debug_print(*args):
            pass
    
    if mesh.type != "MESH":
        return 0
    
    # Find material index in mesh
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
    
    # Create or get attribute
    attr_name = "atlas_mat_index"
    if attr_name not in mesh.data.attributes:
        mesh.data.attributes.new(name=attr_name, type="INT", domain="FACE")
    
    attr = mesh.data.attributes[attr_name]
    
    # Set values for matching faces
    count = 0
    for poly in mesh.data.polygons:
        if poly.material_index == mat_index:
            attr.data[poly.index].value = index
            count += 1
    
    return count


def merge_meshes_for_atlas(
    meshes: List[bpy.types.Object],
    debug_print: Optional[Callable[..., None]] = None,
) -> Optional[bpy.types.Object]:
    """
    Merge meshes for atlas baking.
    
    Args:
        meshes: List of mesh objects to merge
        debug_print: Optional debug function
        
    Returns:
        The merged mesh object, or None if failed
    """
    if debug_print is None:
        def debug_print(*args):
            pass
    
    if not meshes:
        return None
    
    if len(meshes) == 1:
        return meshes[0]
    
    # Select all meshes
    bpy.ops.object.select_all(action="DESELECT")
    for mesh in meshes:
        mesh.select_set(True)
    
    # Make first one active
    bpy.context.view_layer.objects.active = meshes[0]
    
    # Join
    bpy.ops.object.join()
    
    merged = bpy.context.view_layer.objects.active
    debug_print(f"Merged {len(meshes)} meshes -> {merged.name}")
    
    return merged


# -----------------------------------------------------------------------------
# Recombination Shader
# -----------------------------------------------------------------------------


def build_recombination_shader(
    material: bpy.types.Material,
    material_descriptors: List[MaterialDescriptor],
    debug_print: Optional[Callable[..., None]] = None,
) -> bool:
    """
    Build a Mix Shader chain for recombination baking.
    
    Creates a shader that routes to different Principled BSDFs based on
    the atlas_mat_index face attribute, sampling from captured textures.
    
    IMPORTANT: Captured images were baked using ORIGINAL UVs, so we sample
    them with original UVMap. The final bake will write to atlas UV positions
    because `-- Atlas` is set as the active UV layer.
    
    Args:
        material: The material to build the shader in
        material_descriptors: List of MaterialDescriptors with captured images
        debug_print: Optional debug function
        
    Returns:
        True if successful
    """
    if debug_print is None:
        def debug_print(*args):
            pass
    
    if not material.use_nodes:
        material.use_nodes = True
    
    tree = material.node_tree
    nodes = tree.nodes
    links = tree.links
    
    # Clear existing nodes
    nodes.clear()
    
    # Create Material Output
    output_node = nodes.new("ShaderNodeOutputMaterial")
    output_node.location = (800, 0)
    
    # Create Attribute node to read atlas_mat_index
    # For face-domain attributes, we need to use the proper type
    attr_node = nodes.new("ShaderNodeAttribute")
    attr_node.attribute_name = "atlas_mat_index"
    attr_node.attribute_type = "GEOMETRY"  # GEOMETRY reads mesh attributes
    attr_node.location = (-600, 0)
    
    # Debug: Add a viewer to see the attribute value
    # The "Fac" output should give us the scalar value for INT attributes
    # For face-domain INT attributes, Blender should give flat value per face during baking
    
    # Create UV Map node for ORIGINAL UVs (to sample captured images)
    # Captured images were baked using original UVMap, so we sample with same UVs
    uv_node = nodes.new("ShaderNodeUVMap")
    uv_node.uv_map = "UVMap"  # Original UV layer
    uv_node.location = (-800, -200)
    
    # Create Principled BSDF for each material
    principled_nodes = []
    y_offset = 200
    
    for idx, descriptor in enumerate(material_descriptors):
        principled = nodes.new("ShaderNodeBsdfPrincipled")
        principled.name = f"Principled_{descriptor.material_name}"
        principled.location = (0, y_offset)
        
        # Connect captured textures (using original UVMap)
        _connect_captured_textures(
            tree, principled, uv_node, descriptor, y_offset, debug_print
        )
        
        principled_nodes.append(principled)
        y_offset -= 500
    
    if len(principled_nodes) == 0:
        debug_print("    ⚠️ No Principled nodes created")
        return False
    
    # Single material - connect directly
    if len(principled_nodes) == 1:
        links.new(principled_nodes[0].outputs["BSDF"], output_node.inputs["Surface"])
        debug_print("    Connected single material")
        return True
    
    # Multiple materials - build Mix Shader chain
    current_shader = principled_nodes[0].outputs["BSDF"]
    x_offset = 400
    
    for idx in range(1, len(principled_nodes)):
        # Create comparison nodes: atlas_mat_index == idx
        subtract_node = nodes.new("ShaderNodeMath")
        subtract_node.operation = "SUBTRACT"
        subtract_node.location = (-400, -idx * 150)
        links.new(attr_node.outputs["Fac"], subtract_node.inputs[0])
        subtract_node.inputs[1].default_value = float(idx)
        
        abs_node = nodes.new("ShaderNodeMath")
        abs_node.operation = "ABSOLUTE"
        abs_node.location = (-300, -idx * 150)
        links.new(subtract_node.outputs["Value"], abs_node.inputs[0])
        
        compare_node = nodes.new("ShaderNodeMath")
        compare_node.operation = "LESS_THAN"
        compare_node.location = (-200, -idx * 150)
        links.new(abs_node.outputs["Value"], compare_node.inputs[0])
        compare_node.inputs[1].default_value = 0.1
        
        # Create Mix Shader
        mix_node = nodes.new("ShaderNodeMixShader")
        mix_node.location = (x_offset, -idx * 150)
        
        links.new(current_shader, mix_node.inputs[1])
        links.new(principled_nodes[idx].outputs["BSDF"], mix_node.inputs[2])
        links.new(compare_node.outputs["Value"], mix_node.inputs["Fac"])
        
        current_shader = mix_node.outputs["Shader"]
        x_offset += 150
    
    # Connect final output
    links.new(current_shader, output_node.inputs["Surface"])
    debug_print(f"    Built Mix Shader chain for {len(principled_nodes)} materials")
    
    return True


def _connect_captured_textures(
    tree: bpy.types.NodeTree,
    principled: bpy.types.Node,
    uv_node: bpy.types.Node,
    descriptor: MaterialDescriptor,
    y_offset: int,
    debug_print: Callable,
) -> None:
    """
    Connect captured texture images to a Principled BSDF.
    
    Captured images were baked using ORIGINAL UVs, and the uv_node points
    to the original UVMap, so we connect directly without any transforms.
    """
    nodes = tree.nodes
    links = tree.links
    
    x_offset = -400
    connected_count = 0
    
    for format_str, image in descriptor.captured_images.items():
        if not image:
            continue
        
        # Create Image Texture node
        img_node = nodes.new("ShaderNodeTexImage")
        img_node.image = image
        img_node.location = (x_offset, y_offset)
        
        # Connect original UVMap to image texture (no transform needed)
        links.new(uv_node.outputs["UV"], img_node.inputs["Vector"])
        
        # Connect to appropriate input based on format
        _connect_by_format(tree, img_node, principled, format_str, debug_print)
        
        connected_count += 1
        y_offset -= 150


def _connect_by_format(
    tree: bpy.types.NodeTree,
    img_node: bpy.types.Node,
    principled: bpy.types.Node,
    dtp_format: str,
    debug_print: Callable,
) -> None:
    """Connect an image node to Principled BSDF based on DTP format."""
    links = tree.links
    nodes = tree.nodes
    
    format_lower = dtp_format.lower()
    
    if format_lower in ("rgba", "rgb"):
        links.new(img_node.outputs["Color"], principled.inputs["Base Color"])
        if format_lower == "rgba":
            links.new(img_node.outputs["Alpha"], principled.inputs["Alpha"])
    
    elif format_lower in ("normalgl", "normaldx"):
        normal_map = nodes.new("ShaderNodeNormalMap")
        normal_map.location = (img_node.location.x + 200, img_node.location.y)
        links.new(img_node.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])
    
    elif format_lower == "emission":
        links.new(img_node.outputs["Color"], principled.inputs["Emission Color"])
        principled.inputs["Emission Strength"].default_value = 1.0
    
    elif "-" in format_lower:
        # PBR channel pack (e.g., "me-ro-sp")
        channels = format_lower.split("-")
        if len(channels) >= 3:
            sep_rgb = nodes.new("ShaderNodeSeparateColor")
            sep_rgb.mode = "RGB"
            sep_rgb.location = (img_node.location.x + 150, img_node.location.y)
            links.new(img_node.outputs["Color"], sep_rgb.inputs["Color"])
            
            channel_map = {
                "me": "Metallic",
                "ro": "Roughness",
                "sp": "Specular IOR Level",
            }
            
            rgb_outputs = ["Red", "Green", "Blue"]
            for i, ch in enumerate(channels[:3]):
                if ch in channel_map:
                    socket_name = channel_map[ch]
                    if socket_name in principled.inputs:
                        links.new(
                            sep_rgb.outputs[rgb_outputs[i]],
                            principled.inputs[socket_name],
                        )


# -----------------------------------------------------------------------------
# Full Recombination Pipeline
# -----------------------------------------------------------------------------


def execute_atlas_recombination(
    atlas: AtlasDescriptor,
    bake_formats: List[str],
    output_resolution: Optional[Tuple[int, int]] = None,
    debug_print: Optional[Callable[..., None]] = None,
    stop_after_shader_setup: bool = False,
) -> Dict[str, bpy.types.Image]:
    """
    Execute the full atlas recombination pipeline.
    
    Steps:
    1. Apply atlas UV transforms to all meshes
    2. Set face material index attributes
    3. Merge meshes
    4. Create temp material with recombination shader
    5. Bake final atlas textures
    
    Args:
        atlas: The atlas descriptor with material placements
        bake_formats: DTP formats to bake
        output_resolution: Output resolution (defaults to atlas resolution)
        debug_print: Optional debug function
        stop_after_shader_setup: Stop before baking (for debugging)
        
    Returns:
        Dict mapping format -> final baked image
    """
    if debug_print is None:
        def debug_print(*args):
            pass

    if output_resolution is None:
        output_resolution = (atlas.atlas_width, atlas.atlas_height)
    
    debug_print("=" * 50)
    debug_print("ATLAS RECOMBINATION PIPELINE")
    debug_print("=" * 50)
    
    # Step 1: Apply atlas transforms
    debug_print("\n[Step 1] Applying atlas UV transforms...")
    apply_atlas_transforms(atlas, debug_print)
    
    # Step 2: Set face material index attributes
    debug_print("\n[Step 2] Setting face material indices...")
    all_meshes: List[bpy.types.Object] = []
    mat_index = 0
    ordered_descriptors = list(atlas.materials.values())
    
    for descriptor in ordered_descriptors:
        for mesh_name in descriptor.source_mesh_names:
            mesh = bpy.data.objects.get(mesh_name)
            if mesh and mesh.type == "MESH":
                if mesh not in all_meshes:
                    all_meshes.append(mesh)
                
                count = set_face_material_index_attribute(
                    mesh, descriptor.material_name, mat_index, debug_print
                )
                debug_print(f"    {mesh_name}/{descriptor.material_name}: {count} faces")
        mat_index += 1
    
    # Step 3: Merge meshes
    debug_print("\n[Step 3] Merging meshes...")
    merged_mesh = merge_meshes_for_atlas(all_meshes, debug_print)
    if not merged_mesh:
        debug_print("    ⚠️ Failed to merge meshes")
        return {}
    
    
    # Step 4: Create temp material
    debug_print("\n[Step 4] Building recombination shader...")
    temp_name = f"__atlas_recombine_{random.randint(1000, 9999)}"
    temp_material = bpy.data.materials.new(name=temp_name)
    temp_material.use_nodes = True
    
    # Assign to merged mesh
    merged_mesh.data.materials.clear()
    merged_mesh.data.materials.append(temp_material)
    
    # Build shader
    build_recombination_shader(temp_material, ordered_descriptors, debug_print)
    
    if stop_after_shader_setup:
        debug_print("\n⚠️ Stopping after shader setup (debug mode)")
        debug_print(f"    Temp material: {temp_material.name}")
        debug_print(f"    Merged mesh: {merged_mesh.name}")
        return {}
    
    # Step 5: Bake final atlas
    debug_print("\n[Step 5] Baking final atlas textures...")
    from ..image.texture_baker import bake_dtp_texture
    
    results: Dict[str, bpy.types.Image] = {}
    
    for format_idx, dtp_format in enumerate(bake_formats):
        debug_print(f"    Baking {dtp_format}...")
        
        # replace_all_principled mode is destructive - rebuild shader for each format after the first
        if format_idx > 0:
            debug_print(f"      Rebuilding shader for format {dtp_format}...")
            # Clear and rebuild the material
            temp_material.node_tree.nodes.clear()
            build_recombination_shader(temp_material, ordered_descriptors, debug_print)
        
        # CRITICAL: Set active UV layer to "-- Atlas" right before bake
        # Blender's bake operation uses the ACTIVE UV layer
        if merged_mesh.data and merged_mesh.data.uv_layers:
            atlas_uv = merged_mesh.data.uv_layers.get(ATLAS_UV_NAME)
            if atlas_uv:
                merged_mesh.data.uv_layers.active = atlas_uv
                debug_print(f"    Active UV layer set to: {ATLAS_UV_NAME}")
            else:
                debug_print(f"    ⚠️ ERROR: {ATLAS_UV_NAME} UV layer not found!")
        
        # Use bake_dtp_texture with replace_all_principled=True
        # This replaces ALL Principled BSDFs with Emission, preserving Mix Shader routing
        # IMPORTANT: This modifies temp_material, so we rebuild for each format
        result_image = bake_dtp_texture(
            dtp_format=dtp_format,
            obj=merged_mesh,
            material=temp_material,
            resolution=output_resolution,
            max_resolution=output_resolution,
            uv_layer_name=ATLAS_UV_NAME,
            image_type="png",
        )
        
        if result_image:
            results[dtp_format] = result_image
            debug_print(f"      ✅ {dtp_format}: {result_image.size[0]}x{result_image.size[1]}")
        else:
            debug_print(f"      ⚠️ Failed to bake {dtp_format}")
    
    debug_print("\n" + "=" * 50)
    debug_print(f"RECOMBINATION COMPLETE: {len(results)} textures")
    debug_print("=" * 50)
    
    return results


def cleanup_recombination(
    atlas: AtlasDescriptor,
    temp_material: Optional[bpy.types.Material] = None,
    debug_print: Optional[Callable[..., None]] = None,
) -> None:
    """
    Clean up after recombination.
    
    - Removes captured intermediate images
    - Removes temp material
    - Removes atlas UV layers
    
    Args:
        atlas: The atlas descriptor
        temp_material: Optional temp material to remove
        debug_print: Optional debug function
    """
    if debug_print is None:
        def debug_print(*args):
            pass
    
    debug_print("Cleaning up recombination artifacts...")
    
    # Clean up captured images
    from .capture_bake import cleanup_captured_images
    cleanup_captured_images(atlas, debug_print)
    
    # Remove temp material
    if temp_material and temp_material.name in bpy.data.materials:
        bpy.data.materials.remove(temp_material)
        debug_print("    Removed temp material")
    
    debug_print("✅ Cleanup complete")
