"""
Bake execution phase.

Handles baking for each material:
- Single mesh: Direct bake to file
- Multiple meshes: Merge-bake flow with Mix Shader chains
"""

import os
import time
from typing import Dict, List, Optional, Callable, Tuple
import bpy

from .bake_context import BakeContext, BakeImageConfig


def execute_bake_for_material(
    ctx: BakeContext,
    material_name: str,
    meshes: List[bpy.types.Object],
    debug_print: Optional[Callable[..., None]] = None,
    stop_after_node_setup: bool = False,
) -> Dict[str, Tuple[int, int]]:
    """
    Execute baking for a specific material.

    Args:
        ctx: The bake context
        material_name: Name of the material to bake
        meshes: List of mesh objects using this material
        debug_print: Optional debug print function
        stop_after_node_setup: If True, stop after node setup (debug mode)

    Returns:
        Dict mapping format -> (width, height) of final baked images, or empty dict if failed
    """
    if debug_print is None:

        def debug_print(*args):
            pass

    debug_print(f"Executing bake for material: {material_name}")
    debug_print(f"  Mesh count: {len(meshes)}")

    if len(meshes) == 0:
        debug_print("  ⚠️ No meshes to bake")
        return {}

    # Get the material
    material = bpy.data.materials.get(material_name)
    if not material:
        debug_print(f"  ⚠️ Material '{material_name}' not found")
        return {}

    if len(meshes) == 1:
        return _bake_single_mesh(ctx, material, meshes[0], debug_print)
    else:
        return _bake_multi_mesh(
            ctx, material, meshes, debug_print, stop_after_node_setup
        )


def _bake_single_mesh(
    ctx: BakeContext,
    material: bpy.types.Material,
    mesh: bpy.types.Object,
    debug_print: Callable[..., None],
) -> Dict[str, Tuple[int, int]]:
    """
    Bake a single mesh directly.

    When there's only one mesh per material, we can bake directly.

    Returns:
        Dict mapping format -> (width, height) of final baked images
    """
    debug_print(f"  Single mesh bake: {mesh.name}")

    # Import texture baker
    from ..image.texture_baker import bake_dtp_texture

    resolutions = {}
    for img_config in ctx.bake_images:
        debug_print(f"    Baking {img_config.format}...")

        # Determine resolution
        resolution = None
        max_resolution = (img_config.width, img_config.height)
        if not img_config.optimize_resolution:
            resolution = max_resolution

        # Bake using existing baker
        result_image = bake_dtp_texture(
            dtp_format=img_config.format,
            obj=mesh,
            material=material,
            resolution=resolution,
            max_resolution=max_resolution,
            uv_layer_name=_get_first_uv_name(mesh),  # Use first UV
        )

        if not result_image:
            debug_print(f"    ⚠️ Failed to bake {img_config.format}")
            continue

        # Store final resolution
        resolutions[img_config.format] = (result_image.size[0], result_image.size[1])

        # Save or pack based on context settings
        if ctx.save_to_file and ctx.export_dir:
            _save_image_to_file(
                result_image, ctx, material.name, img_config, debug_print
            )
        else:
            debug_print(f"    ✅ Baked {img_config.format} (packed in .blend)")

    return resolutions


def _bake_multi_mesh(
    ctx: BakeContext,
    material: bpy.types.Material,
    meshes: List[bpy.types.Object],
    debug_print: Callable[..., None],
    stop_after_node_setup: bool = False,
) -> Dict[str, Tuple[int, int]]:
    """
    Multi-mesh baking when material is on 2+ meshes.

    Flow:
    1. Bake each object individually and keep internally
    2. Wipe 2nd+ UVs on all of them
    3. Rename 1st UV to "UVMap"
    4. Set face custom attribute by mesh index
    5. Merge the meshes
    6. Assign a new Material with temp name
    7. Setup Principled BSDF per original mesh with baked images
    8. Setup Mix Shader chain keyed by face custom attribute
    9. Bake final image to file path

    Args:
        ctx: Bake context
        material: Original material
        meshes: List of mesh objects using this material
        debug_print: Debug print function
        stop_after_node_setup: If True, stop after node setup (for debugging)
    """
    debug_print(f"  Multi-mesh bake: {len(meshes)} meshes")

    from ..image.texture_baker import bake_dtp_texture

    # Store baked images per mesh: {mesh_name: {format: image}}
    baked_images_per_mesh: Dict[str, Dict[str, bpy.types.Image]] = {}

    # Determine consolidated DTP formats for intermediate steps
    # This prevents creating weird custom formats for the temporary material setup
    intermediate_configs = _get_intermediate_bake_configs(ctx.bake_images)
    debug_print(
        f"    Consolidated intermediate formats: {[c.format for c in intermediate_configs]}"
    )

    debug_print("  Baking each mesh individually...")

    for mesh in meshes:
        mesh_name = mesh.name
        baked_images_per_mesh[mesh_name] = {}

        for img_config in intermediate_configs:
            debug_print(f"    Baking {mesh_name} / {img_config.format}...")

            resolution = None
            max_resolution = (img_config.width, img_config.height)
            # Intermediate bakes: always use max resolution specified in config
            resolution = max_resolution

            result_image = bake_dtp_texture(
                dtp_format=img_config.format,
                obj=mesh,
                material=material,
                resolution=resolution,
                max_resolution=max_resolution,
                uv_layer_name=_get_first_uv_name(mesh),
            )

            if result_image:
                baked_images_per_mesh[mesh_name][img_config.format] = result_image
                debug_print(f"      ✅ Baked {img_config.format}")
            else:
                debug_print(f"      ⚠️ Failed to bake {img_config.format}")

    debug_print("  Wiping extra UV layers...")
    for mesh in meshes:
        _wipe_extra_uv_layers(mesh, debug_print)

    debug_print("  Renaming first UV to 'UVMap'...")
    for mesh in meshes:
        _rename_first_uv(mesh, "UVMap", debug_print)

    debug_print("  Setting face mesh index attributes...")
    mesh_names = []  # Store names as objects will be invalid after join
    for idx, mesh in enumerate(meshes):
        mesh_names.append(mesh.name)
        _set_face_mesh_index(mesh, idx, debug_print)

    debug_print("  Merging meshes...")
    merged_mesh = _merge_meshes(meshes, debug_print)
    if not merged_mesh:
        debug_print("    ⚠️ Failed to merge meshes")
        return False

    debug_print("  Creating temp material...")
    temp_material = _create_temp_material(material.name, debug_print)

    # Assign to merged mesh
    merged_mesh.data.materials.clear()
    merged_mesh.data.materials.append(temp_material)

    debug_print("  Setting up Mix Shader material...")
    _setup_mix_shader_material(
        temp_material,
        mesh_names,  # Pass names strings, not objects
        baked_images_per_mesh,
        ctx.bake_images,
        debug_print,
    )

    # Stop here if requested (for debugging node setup)
    if stop_after_node_setup:
        debug_print("  ⚠️ Stopping after node setup (debug mode)")
        debug_print(f"  Temp material: {temp_material.name}")
        debug_print(f"  Merged mesh: {merged_mesh.name}")
        return {}

    debug_print("  Baking final merged image...")
    resolutions = {}
    for img_config in ctx.bake_images:
        debug_print(f"    Baking final {img_config.format}...")

        resolution = None
        max_resolution = (img_config.width, img_config.height)
        if not img_config.optimize_resolution:
            resolution = max_resolution

        result_image = bake_dtp_texture(
            dtp_format=img_config.format,
            obj=merged_mesh,
            material=temp_material,
            resolution=resolution,
            max_resolution=max_resolution,
            uv_layer_name="UVMap",
        )

        if result_image:
            # Store final resolution
            resolutions[img_config.format] = (result_image.size[0], result_image.size[1])
            
            if ctx.save_to_file and ctx.export_dir:
                _save_image_to_file(
                    result_image, ctx, material.name, img_config, debug_print
                )
            debug_print(f"    ✅ Final bake {img_config.format}")
        else:
            debug_print(f"    ⚠️ Failed final bake {img_config.format}")

    # Clean up intermediate images
    debug_print("  Cleaning up intermediate images...")
    for mesh_name, images in baked_images_per_mesh.items():
        for format_name, image in images.items():
            bpy.data.images.remove(image)

    return resolutions


def _get_intermediate_bake_configs(
    bake_configs: List[BakeImageConfig],
) -> List[BakeImageConfig]:
    """
    Determine consolidated DTP formats for intermediate steps.

    Instead of baking the exact requested formats (which might be complex like "me-sp-ro"),
    we bake standard components that cover all needs.

    Mapping:
    - Any Color/Albedo -> "rgba"
    - Any Normal -> "normalgl"
    - Any PBR (Met/Rough/Spec/AO) -> "me-ro-sp"
    - Any Emission -> "emission"
    """
    targets = set()

    dtp_category_map = {
        "rgba": ["cr", "cg", "cb", "al", "lr", "lg", "lb", "rgba", "rgb"],
        "normalgl": ["nx", "nd", "ng", "normaldx", "normalgl"],
        "me-ro-sp": ["me", "ro", "sp", "ao", "sm"],
        "emission": ["er", "eg", "eb", "es", "emission"],
    }

    for cfg in bake_configs:
        fmt = cfg.format.lower()

        # Check against categories
        for target, keywords in dtp_category_map.items():
            if target in targets:
                continue  # Already added

            # If standard format name matches
            if fmt == target:
                targets.add(target)
                continue

            # Check for channels in format string
            # Handle dash-separated generic format or just generic keyword search
            # (simple substring check "al" in "normal" can return false positive)
            # Safe parsing: split by '-'
            channels = fmt.split("-")

            # Check exact match in channel list
            found = False
            for kw in keywords:
                if kw in channels or fmt == kw:
                    targets.add(target)
                    found = True
                    break
            if found:
                continue

    if not bake_configs:
        return []

    # Use max resolution found across configs to ensure quality
    max_w = max(cfg.width for cfg in bake_configs)
    max_h = max(cfg.height for cfg in bake_configs)

    inter_configs = []
    for t in targets:
        inter_configs.append(
            BakeImageConfig(
                format=t,
                image_type="png",
                width=max_w,
                height=max_h,
                optimize_resolution=False,
            )
        )

    return inter_configs


def _get_first_uv_name(obj: bpy.types.Object) -> Optional[str]:
    """Get the name of the first UV layer on an object."""
    if obj.type != "MESH" or not obj.data.uv_layers:
        return None
    return obj.data.uv_layers[0].name


def _wipe_extra_uv_layers(obj: bpy.types.Object, debug_print: Callable) -> None:
    """Remove all UV layers except the first one."""
    if obj.type != "MESH":
        return

    mesh = obj.data
    while len(mesh.uv_layers) > 1:
        # Remove the last one
        last_uv = mesh.uv_layers[-1]
        debug_print(f"    Removing UV: {last_uv.name} from {obj.name}")
        mesh.uv_layers.remove(last_uv)


def _rename_first_uv(
    obj: bpy.types.Object, new_name: str, debug_print: Callable
) -> None:
    """Rename the first UV layer."""
    if obj.type != "MESH" or not obj.data.uv_layers:
        return

    first_uv = obj.data.uv_layers[0]
    old_name = first_uv.name
    if old_name != new_name:
        first_uv.name = new_name
        debug_print(f"    Renamed UV: {old_name} -> {new_name} on {obj.name}")


def _set_face_mesh_index(
    obj: bpy.types.Object,
    mesh_index: int,
    debug_print: Callable,
) -> None:
    """
    Set a face custom attribute on all faces of a mesh.

    The attribute is named "mesh_index" and stores the mesh index as an integer.
    """
    if obj.type != "MESH":
        return

    mesh = obj.data

    # Create or get the attribute
    attr_name = "mesh_index"
    if attr_name not in mesh.attributes:
        mesh.attributes.new(name=attr_name, type="INT", domain="FACE")

    attr = mesh.attributes[attr_name]

    # Set all face values to the mesh index
    for i in range(len(attr.data)):
        attr.data[i].value = mesh_index

    debug_print(
        f"    Set mesh_index={mesh_index} on {len(attr.data)} faces of {obj.name}"
    )


def _merge_meshes(
    meshes: List[bpy.types.Object],
    debug_print: Callable,
) -> Optional[bpy.types.Object]:
    """Merge multiple meshes into one."""
    if len(meshes) == 0:
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
    debug_print(f"    Merged {len(meshes)} meshes -> {merged.name}")

    return merged


def _create_temp_material(base_name: str, debug_print: Callable) -> bpy.types.Material:
    """Create a new temporary material for baking."""
    import random

    temp_name = f"__bake_temp_{base_name}_{random.randint(1000, 9999)}"
    mat = bpy.data.materials.new(name=temp_name)
    mat.use_nodes = True
    debug_print(f"    Created temp material: {temp_name}")
    return mat


def _setup_mix_shader_material(
    material: bpy.types.Material,
    original_mesh_names: List[str],
    baked_images: Dict[str, Dict[str, bpy.types.Image]],
    bake_configs: List[BakeImageConfig],
    debug_print: Callable,
) -> None:
    """
    Setup material for multi-mesh baking using Mix Shader chains.

    Creates:
    - One Principled BSDF per original mesh with baked textures connected
    - Mix Shader nodes chained together to select based on face mesh_index attribute
    - Connects final Mix Shader output to Material Output
    """
    tree = material.node_tree
    nodes = tree.nodes
    links = tree.links

    # Clear existing nodes
    nodes.clear()

    # Create Material Output
    output_node = nodes.new("ShaderNodeOutputMaterial")
    output_node.location = (600, 0)

    # Create Attribute node to read mesh_index
    attr_node = nodes.new("ShaderNodeAttribute")
    attr_node.attribute_name = "mesh_index"
    attr_node.attribute_type = "GEOMETRY"
    attr_node.location = (-400, 0)

    # Create Principled BSDF nodes for each mesh
    principled_nodes = []
    y_offset = 0
    for idx, mesh_name in enumerate(original_mesh_names):
        # Create Principled BSDF
        principled = nodes.new("ShaderNodeBsdfPrincipled")
        principled.name = f"Principled_{idx}"
        principled.location = (-200, y_offset)

        # Connect baked textures to Principled BSDF
        images_for_mesh = baked_images.get(mesh_name, {})
        _connect_baked_textures_to_principled(
            tree,
            principled,
            images_for_mesh,
            bake_configs,
            y_offset,
            debug_print,
        )

        principled_nodes.append(principled)
        y_offset -= 400

    if len(principled_nodes) == 0:
        debug_print("    ⚠️ No Principled BSDF nodes created")
        return

    # If only one mesh, connect directly
    if len(principled_nodes) == 1:
        links.new(principled_nodes[0].outputs["BSDF"], output_node.inputs["Surface"])
        debug_print("    Connected single Principled BSDF to output")
        return

    # Chain Mix Shader nodes together
    # For each mesh index > 0, create a comparison and mix node
    current_shader = principled_nodes[0].outputs["BSDF"]
    x_offset = 200

    for idx in range(1, len(principled_nodes)):
        # Create comparison: mesh_index == idx
        # Use subtract + absolute + less_than to check equality
        # Subtract: mesh_index - idx
        subtract_node = nodes.new("ShaderNodeMath")
        subtract_node.operation = "SUBTRACT"
        subtract_node.location = (-400, -idx * 200)
        links.new(attr_node.outputs["Fac"], subtract_node.inputs[0])
        subtract_node.inputs[1].default_value = float(idx)

        # Absolute: |mesh_index - idx|
        abs_node = nodes.new("ShaderNodeMath")
        abs_node.operation = "ABSOLUTE"
        abs_node.location = (-300, -idx * 200)
        links.new(subtract_node.outputs["Value"], abs_node.inputs[0])

        # Less than: |mesh_index - idx| < 0.1 (equality check with tolerance)
        compare_node = nodes.new("ShaderNodeMath")
        compare_node.operation = "LESS_THAN"
        compare_node.location = (-200, -idx * 200)
        links.new(abs_node.outputs["Value"], compare_node.inputs[0])
        compare_node.inputs[1].default_value = 0.1

        # Create Mix Shader node
        mix_node = nodes.new("ShaderNodeMixShader")
        mix_node.location = (x_offset, -idx * 200)

        # Connect previous shader to Shader input
        links.new(current_shader, mix_node.inputs[1])

        # Connect current Principled BSDF to Shader input
        links.new(principled_nodes[idx].outputs["BSDF"], mix_node.inputs[2])

        # Connect comparison result to Fac input
        links.new(compare_node.outputs["Value"], mix_node.inputs["Fac"])

        # Update current shader for next iteration
        current_shader = mix_node.outputs["Shader"]
        x_offset += 200

        debug_print(f"    Created Mix Shader chain for mesh {idx}")

    # Connect final Mix Shader output to Material Output
    links.new(current_shader, output_node.inputs["Surface"])
    debug_print(f"    Mix Shader chain setup complete ({len(principled_nodes)} meshes)")


def _connect_baked_textures_to_principled(
    tree: bpy.types.NodeTree,
    principled: bpy.types.Node,
    images: Dict[str, bpy.types.Image],
    bake_configs: List[BakeImageConfig],
    y_offset: int,
    debug_print: Callable,
) -> None:
    """Connect baked texture images to a Principled BSDF node."""
    from ..image.dtp_format import expand_alias, is_alias

    nodes = tree.nodes
    links = tree.links

    x_offset = -600

    for format_str, image in images.items():
        if not image:
            continue

        # Create Image Texture node
        img_node = nodes.new("ShaderNodeTexImage")
        img_node.image = image
        img_node.location = (x_offset, y_offset)

        # Add UV Map node to ensure we use the correct UV
        uv_node = nodes.new("ShaderNodeUVMap")
        uv_node.uv_map = "UVMap"
        uv_node.location = (x_offset - 200, y_offset)
        links.new(uv_node.outputs["UV"], img_node.inputs["Vector"])

        # Determine how to connect based on DTP format
        _connect_by_dtp_format(tree, img_node, principled, format_str, debug_print)

        y_offset -= 150


def _connect_by_dtp_format(
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

    # Handle common aliases
    if format_lower in ("rgba", "rgb"):
        links.new(img_node.outputs["Color"], principled.inputs["Base Color"])
        if format_lower == "rgba" and "Alpha" in img_node.outputs:
            links.new(img_node.outputs["Alpha"], principled.inputs["Alpha"])
        debug_print(f"      Connected {dtp_format} -> Base Color")

    elif format_lower in ("normalgl", "normaldx"):
        # Add Normal Map node
        normal_map = nodes.new("ShaderNodeNormalMap")
        normal_map.location = (img_node.location.x + 200, img_node.location.y)
        links.new(img_node.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])
        debug_print(f"      Connected {dtp_format} -> Normal")

    elif format_lower == "emission":
        links.new(img_node.outputs["Color"], principled.inputs["Emission Color"])
        principled.inputs["Emission Strength"].default_value = 1.0
        debug_print(f"      Connected {dtp_format} -> Emission")

    else:
        # Parse channel format (e.g., "me-ro-sp" or "me-sp-ro")
        channels = format_lower.split("-")
        if len(channels) >= 3:
            # Create Separate Color node
            sep_rgb = nodes.new("ShaderNodeSeparateColor")
            sep_rgb.mode = "RGB"
            sep_rgb.location = (img_node.location.x + 150, img_node.location.y)
            links.new(img_node.outputs["Color"], sep_rgb.inputs["Color"])

            channel_map = {
                "me": "Metallic",
                "ro": "Roughness",
                "sp": "Specular IOR Level",
                "ao": "Ambient Occlusion",  # Not in Principled 4.x/5.x
                "sm": "Roughness",  # Inverted
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
                        debug_print(f"      Connected {ch} -> {socket_name}")


def _save_image_to_file(
    image: bpy.types.Image,
    ctx: BakeContext,
    material_name: str,
    img_config: BakeImageConfig,
    debug_print: Callable,
) -> None:
    """Save a baked image to file."""
    from ..common.file_stuff import sanitize_name

    # Determine filename
    if ctx.filename_formatter:
        ext = "png" if img_config.image_type == "png" else "exr"
        filename = ctx.filename_formatter(material_name, img_config.format, ext)
    else:
        clean_name = sanitize_name(material_name, strict=True)
        ext = "png" if img_config.image_type == "png" else "exr"
        filename = f"{clean_name}.{img_config.format}.{ext}"

    filepath = os.path.join(ctx.export_dir, filename)
    os.makedirs(
        os.path.dirname(filepath) if os.path.dirname(filepath) else ctx.export_dir,
        exist_ok=True,
    )

    # Set file format and save
    image.filepath_raw = filepath
    if img_config.image_type == "png":
        image.file_format = "PNG"
    else:
        image.file_format = "OPEN_EXR"

    image.save()
    debug_print(f"    💾 Saved: {filepath}")
