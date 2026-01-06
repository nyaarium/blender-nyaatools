"""Texture baking utilities for rendering Blender material sockets to texture maps."""

import bpy
import time
from typing import Optional, Tuple

from .material_analyzer import find_principled_bsdf, detect_best_resolution
from .node_graph_state import NodeGraphState
from .dtp_format import is_flag_supported, expand_alias, is_alias
from .uv.analyze_mip_stats import analyze_mip_stats
from .texture_utils import resize_image_to_size
from .texture_utils import _image_to_np, _np_to_image_pixels


# Constants
BAKE_MARGIN = 256


def _get_bake_margin(resolution: Tuple[int, int]) -> int:
    """
    Calculate appropriate bake margin based on resolution.
    For very small textures, use a smaller margin to avoid processing overhead.
    """
    width, height = resolution
    min_dimension = min(width, height)
    # For textures smaller than 256px, use a margin proportional to size
    # For larger textures, use the full 256px margin
    if min_dimension < 256:
        # Use 1/4 of the smallest dimension, min 8
        return max(8, min_dimension // 4)
    return BAKE_MARGIN


# DTP channel mapping for sockets and texture baking
DTP_SOCKET_MAP = {
    # Constant values
    "0": "__CONSTANT_0__",  # Constant 0.0 (black)
    "1": "__CONSTANT_1__",  # Constant 1.0 (white)
    "xx": "__UNUSED__",  # Unused/omit channel (only valid for alpha position)
    # Direct sockets (grayscale/scalar values)
    "me": "Metallic",
    "sp": "Specular IOR Level",
    "ro": "Roughness",
    "al": "Alpha",
    "ao": "Ambient Occlusion",
    "he": "Height",
    "es": "Emission Strength",
    "sm": "Roughness",  # Smoothness (inverted roughness)
    # RGB sockets (need Separate RGB for individual channels)
    "cr": ("Base Color", 0),  # R channel
    "cg": ("Base Color", 1),  # G channel
    "cb": ("Base Color", 2),  # B channel
    "er": ("Emission Color", 0),  # R channel
    "eg": ("Emission Color", 1),  # G channel
    "eb": ("Emission Color", 2),  # B channel
    "nx": ("Normal", 0),  # R channel
    "ng": ("Normal", 1),  # G channel (OpenGL)
    "nd": ("Normal", 1),  # G channel (DirectX, inverted)
    # Linear color channels (for HDR workflows)
    "lr": ("Base Color", 0),  # Linear R channel
    "lg": ("Base Color", 1),  # Linear G channel
    "lb": ("Base Color", 2),  # Linear B channel
    # Special cases for normal maps (uses NORMAL bake type)
    "normalgl": "Normal",
    "normaldx": "Normal",
}


def bake_dtp_texture(
    dtp_format: str,
    obj: bpy.types.Object,
    material: bpy.types.Material,
    resolution: Optional[Tuple[int, int]] = None,
    max_resolution: Optional[Tuple[int, int]] = None,
) -> Optional[bpy.types.Image]:
    def debug_print(*msgs):
        print("        ", *msgs)
        return

    if not material.use_nodes:
        return None

    # Parse format string to channels
    try:
        channels = _parse_format_string(dtp_format)
    except ValueError as e:
        debug_print(f"ERROR: {e}")
        return None

    # Determine bake type
    bake_type = _get_bake_type_for_channels(channels)

    # Find Principled BSDF and determine which tree it's in
    principled_result = find_principled_bsdf(material)
    if not principled_result:
        return None

    original_material_output = principled_result["material_output"]
    principled_bsdf = principled_result["principled_bsdf"]
    tree_stack = principled_result["tree_stack"]
    principled_tree = tree_stack[
        -1
    ]  # Last tree in stack is where principled BSDF is located

    # Create state tracker for safe node manipulation
    shader_state = NodeGraphState(material, material.node_tree, principled_tree)

    # Blender 5.0+: Must fully remove Material Output, not just detach
    # Store info to recreate it later
    root_tree = material.node_tree
    original_output_location = (
        original_material_output.location.x,
        original_material_output.location.y,
    )
    original_output_surface_link = None
    surface_input = original_material_output.inputs.get("Surface")
    if surface_input and surface_input.is_linked:
        link = surface_input.links[0]
        original_output_surface_link = (link.from_node.name, link.from_socket.name)

    # Delete the original Material Output (required for Blender 5.0+ baking)
    root_tree.nodes.remove(original_material_output)
    original_material_output = None  # Mark as deleted

    # Ensure UV map exists
    if not _ensure_uv_map(obj):
        debug_print(f"Warning: Could not ensure UV map for object {obj.name}")
        return None

    # Store original render settings
    scene = bpy.context.scene
    original_engine = scene.render.engine
    original_samples = scene.cycles.samples if hasattr(scene, "cycles") else None
    original_film_transparent = scene.render.film_transparent

    # Setup render settings for baking
    scene.render.engine = "CYCLES"
    scene.render.film_transparent = False
    if hasattr(scene, "cycles"):
        scene.cycles.samples = 1

    # Setup object selection and context
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Ensure we're in OBJECT mode
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    try:
        if bake_type == "NORMAL":
            # Stage normal node and determine resolution
            normal_output_node, detected_resolution = _stage_normal_node(
                tree_stack, principled_bsdf, resolution, max_resolution, debug_print
            )
            if not normal_output_node:
                return None

            # Determine final resolution
            final_resolution = resolution or detected_resolution or (512, 512)
            if max_resolution:
                max_width, max_height = max_resolution
                final_resolution = (
                    min(final_resolution[0], max_width),
                    min(final_resolution[1], max_height),
                )

            # Bake normal
            result = _bake_normal_output(
                dtp_format,
                material,
                shader_state,
                material.node_tree,
                principled_tree,
                normal_output_node,
                final_resolution,
                debug_print,
            )

        else:  # EMIT
            # Stage emission nodes and determine resolution
            rgb_output_node, alpha_output_node, final_resolution = (
                _stage_emission_nodes(
                    tree_stack,
                    channels,
                    shader_state,
                    principled_bsdf,
                    principled_tree,
                    resolution,
                    max_resolution,
                    debug_print,
                )
            )
            if not rgb_output_node:
                return None

            # Apply user resolution override and max cap
            if resolution:
                final_resolution = resolution
            elif max_resolution:
                max_width, max_height = max_resolution
                final_resolution = (
                    min(final_resolution[0], max_width),
                    min(final_resolution[1], max_height),
                )

            # Bake emission
            result = _bake_emission_output(
                dtp_format,
                material,
                shader_state,
                material.node_tree,
                rgb_output_node,
                alpha_output_node,
                final_resolution,
                debug_print,
            )

        if not result:
            return None

        # Apply optimization if user didn't specify resolution
        if resolution is None:
            result = _optimize_baked_image(result, obj, max_resolution)

        return result

    except Exception as e:
        debug_print(f"ERROR: Failed to bake DTP texture {dtp_format}: {e}")
        import traceback

        traceback.print_exc()
        return None

    finally:
        # Restore shader state (clean up temporary nodes and connections)
        shader_state.restore()

        # Recreate the original Material Output that we deleted
        restored_output = root_tree.nodes.new("ShaderNodeOutputMaterial")
        restored_output.location = original_output_location
        restored_output.is_active_output = True

        # Restore the Surface connection if there was one
        if original_output_surface_link:
            from_node_name, from_socket_name = original_output_surface_link
            from_node = root_tree.nodes.get(from_node_name)
            if from_node:
                from_socket = from_node.outputs.get(from_socket_name)
                if from_socket:
                    root_tree.links.new(from_socket, restored_output.inputs["Surface"])

        # Restore render settings
        scene.render.engine = original_engine
        scene.render.film_transparent = original_film_transparent
        if original_samples is not None and hasattr(scene, "cycles"):
            scene.cycles.samples = original_samples


def _stage_normal_node(
    tree_stack: list,
    principled_bsdf: bpy.types.ShaderNode,
    resolution: Optional[Tuple[int, int]],
    max_resolution: Optional[Tuple[int, int]],
    debug_print,
) -> Tuple[Optional[object], Optional[Tuple[int, int]]]:
    # Get Normal socket from Principled BSDF
    normal_socket = principled_bsdf.inputs.get("Normal")
    if not normal_socket:
        debug_print("Normal socket not found")
        return None, None

    # Determine resolution
    if resolution:
        # User specified resolution
        final_resolution = resolution
    else:
        # Detect from normal socket
        if normal_socket.is_linked:
            final_resolution = detect_best_resolution(normal_socket, tree_stack)
        else:
            # Unconnected normal socket - use default
            final_resolution = (1024, 1024)

    # Apply max_resolution cap
    if max_resolution and final_resolution:
        max_width, max_height = max_resolution
        final_resolution = (
            min(final_resolution[0], max_width),
            min(final_resolution[1], max_height),
        )

    # Return the normal socket (will be connected to Material Output during baking)
    return normal_socket, final_resolution


def _stage_emission_nodes(
    tree_stack: list,
    channels: list,
    shader_state: NodeGraphState,
    principled_bsdf: bpy.types.Node,
    principled_tree: bpy.types.NodeTree,
    resolution: Optional[Tuple[int, int]],
    max_resolution: Optional[Tuple[int, int]],
    debug_print,
) -> Tuple[Optional[object], Optional[object], Optional[Tuple[int, int]]]:
    if len(channels) > 4:
        debug_print(f"Too many channels for RGB/Alpha: {len(channels)}")
        return None, None, None

    # Create RGB emission node
    rgb_emission = shader_state.add_node(principled_tree, "ShaderNodeEmission")

    # Create Combine Color node for RGB channels
    combine_rgb_node = shader_state.add_node(principled_tree, "ShaderNodeCombineColor")
    combine_rgb_node.mode = "RGB"

    # Create Separate Color nodes for all colored DTP channels

    # Analyze all channels to determine which sockets need Separate Color nodes
    separate_nodes = {}
    for channel in channels:
        socket_mapping = DTP_SOCKET_MAP.get(channel)
        if isinstance(socket_mapping, tuple):
            socket_name, _ = socket_mapping
            if socket_name not in separate_nodes:
                socket = principled_bsdf.inputs.get(socket_name)
                if socket and socket.is_linked:
                    # Create Separate Color node once per socket
                    separate_rgb = shader_state.add_node(
                        principled_tree, "ShaderNodeSeparateColor"
                    )
                    separate_rgb.mode = "RGB"
                    from_socket = socket.links[0].from_socket
                    shader_state.connect_sockets(
                        principled_tree,
                        from_socket.node,
                        from_socket.name,
                        separate_rgb,
                        "Color",
                        f"separate {socket_name}",
                    )
                    separate_nodes[socket_name] = separate_rgb

    # Connect RGB channels to Combine Color
    _make_shader_nodes(
        channels[:3],
        shader_state,
        principled_tree,
        principled_bsdf,
        separate_nodes,
        combine_rgb_node,
        False,
        debug_print,
    )

    # Connect Combine Color output → RGB Emission Color
    shader_state.connect_sockets(
        principled_tree,
        combine_rgb_node,
        "Color",
        rgb_emission,
        "Color",
        "combine RGB to emission",
    )

    # Handle Alpha channel if present (4th channel)
    alpha_emission = None

    if len(channels) == 4:
        # Alpha channel detected for RGBA baking

        alpha_channel = channels[3]

        alpha_emission = shader_state.add_node(principled_tree, "ShaderNodeEmission")

        # Use _make_shader_nodes for alpha channel with scalar flag
        _make_shader_nodes(
            [alpha_channel],
            shader_state,
            principled_tree,
            principled_bsdf,
            separate_nodes,
            alpha_emission,
            True,
            debug_print,
        )

    # Determine final resolution (use max of RGB and Alpha if both exist)
    if resolution:
        final_resolution = resolution
    else:
        # Check RGB resolution
        r_connected = combine_rgb_node.inputs["Red"].is_linked
        g_connected = combine_rgb_node.inputs["Green"].is_linked
        b_connected = combine_rgb_node.inputs["Blue"].is_linked
        has_rgb_connected = r_connected or g_connected or b_connected

        if not has_rgb_connected:
            rgb_resolution = (8, 8)
        else:
            rgb_resolution = detect_best_resolution(
                rgb_emission.inputs["Color"], tree_stack
            )

        # Check Alpha resolution if present
        if alpha_emission:
            if not alpha_emission.inputs["Color"].is_linked:
                alpha_resolution = (8, 8)
            else:
                alpha_resolution = detect_best_resolution(
                    alpha_emission.inputs["Color"], tree_stack
                )

            # Use max of RGB and Alpha
            final_resolution = (
                max(rgb_resolution[0], alpha_resolution[0]),
                max(rgb_resolution[1], alpha_resolution[1]),
            )
        else:
            final_resolution = rgb_resolution

    # Apply max_resolution cap
    if max_resolution and final_resolution:
        max_width, max_height = max_resolution
        final_resolution = (
            min(final_resolution[0], max_width),
            min(final_resolution[1], max_height),
        )

    return rgb_emission, alpha_emission, final_resolution


def _bake_emission_output(
    dtp_format: str,
    material: bpy.types.Material,
    shader_state: NodeGraphState,
    root_tree: bpy.types.NodeTree,
    rgb_output_node: object,
    alpha_output_node: Optional[object],
    resolution: Tuple[int, int],
    debug_print,
) -> Optional[bpy.types.Image]:
    # Create temporary Material Output node in the same tree as the emission node
    emission_tree = rgb_output_node.id_data

    temp_material_output = shader_state.add_node(
        emission_tree, "ShaderNodeOutputMaterial"
    )
    temp_material_output.is_active_output = True

    # Determine if we're baking RGBA or just RGB
    has_alpha = alpha_output_node is not None
    bake_type = "RGBA" if has_alpha else "RGB"
    debug_print(f"🍞 Baking {bake_type} at {resolution[0]}x{resolution[1]}")

    # Create RGB target image
    rgb_image = bpy.data.images.new(
        name=f"bake_{material.name}_{dtp_format}_rgb",
        width=resolution[0],
        height=resolution[1],
        alpha=False,
        float_buffer=False,
    )

    # Create image texture node in ROOT tree
    img_node = shader_state.add_node(root_tree, "ShaderNodeTexImage")
    img_node.image = rgb_image
    img_node.select = True
    root_tree.nodes.active = img_node

    # Connect RGB emission to Material Output
    shader_state.connect_sockets(
        emission_tree,
        rgb_output_node,
        "Emission",
        temp_material_output,
        "Surface",
        "RGB emission to material output",
    )

    # Perform RGB bake
    bake_start_time = time.time()
    margin = _get_bake_margin(resolution)
    bpy.ops.object.bake(type="EMIT", margin=margin, use_selected_to_active=False)
    bake_end_time = time.time()
    rgb_duration = int(bake_end_time - bake_start_time)

    if not alpha_output_node:
        # RGB-only baking
        debug_print(f"    ✔️ RGB:   {rgb_duration} seconds")
        return rgb_image

    # Create Alpha target image
    alpha_image = bpy.data.images.new(
        name=f"bake_{material.name}_{dtp_format}_alpha",
        width=resolution[0],
        height=resolution[1],
        alpha=False,
        float_buffer=False,
    )

    # Update image texture node for alpha
    img_node.image = alpha_image

    # Connect Alpha emission to Material Output
    shader_state.detach_socket(temp_material_output.inputs["Surface"])
    shader_state.connect_sockets(
        emission_tree,
        alpha_output_node,
        "Emission",
        temp_material_output,
        "Surface",
        "Alpha emission to material output",
    )

    # Perform Alpha bake
    bake_start_time = time.time()
    margin = _get_bake_margin(resolution)
    bpy.ops.object.bake(type="EMIT", margin=margin, use_selected_to_active=False)
    bake_end_time = time.time()
    alpha_duration = int(bake_end_time - bake_start_time)

    # Display timing results with checkmarks
    debug_print(f"    ✔️ RGB:   {rgb_duration} seconds")
    debug_print(f"    ✔️ Alpha: {alpha_duration} seconds")

    # Pack RGB + Alpha together
    final_image = _pack_rgba_images(
        material, dtp_format, rgb_image, alpha_image, resolution, debug_print
    )

    # Clean up intermediate images
    bpy.data.images.remove(rgb_image)
    bpy.data.images.remove(alpha_image)

    return final_image


def _bake_normal_output(
    dtp_format: str,
    material: bpy.types.Material,
    shader_state: NodeGraphState,
    root_tree: bpy.types.NodeTree,
    principled_tree: bpy.types.NodeTree,
    normal_output_node: object,
    resolution: Tuple[int, int],
    debug_print,
) -> Optional[bpy.types.Image]:
    # Create target image
    target_image = bpy.data.images.new(
        name=f"bake_{material.name}_{dtp_format}",
        width=resolution[0],
        height=resolution[1],
        alpha=False,
        float_buffer=False,
    )

    # Create image texture node in ROOT tree
    img_node = shader_state.add_node(root_tree, "ShaderNodeTexImage")
    img_node.image = target_image
    img_node.select = True
    root_tree.nodes.active = img_node

    # Create temporary Principled BSDF for normal baking in the same tree as the normal output
    temp_principled = shader_state.add_node(principled_tree, "ShaderNodeBsdfPrincipled")

    # Create temporary Material Output node in the same tree as the Principled BSDF
    temp_material_output = shader_state.add_node(
        principled_tree, "ShaderNodeOutputMaterial"
    )

    # Connect normal map texture to temp Principled BSDF's Normal input
    if hasattr(normal_output_node, "is_linked") and normal_output_node.is_linked:
        from_socket = normal_output_node.links[0].from_socket
        shader_state.connect_sockets(
            principled_tree,
            from_socket.node,
            from_socket.name,
            temp_principled,
            "Normal",
            "normal map to temp principled",
        )

    # Connect temp Principled BSDF to Material Output (both in principled_tree)
    shader_state.connect_sockets(
        principled_tree,
        temp_principled,
        "BSDF",
        temp_material_output,
        "Surface",
        "temp principled to material output",
    )

    # Perform the bake
    debug_print(f"🍞 Baking Normal at {resolution[0]}x{resolution[1]}")
    bake_start_time = time.time()
    margin = _get_bake_margin(resolution)
    bpy.ops.object.bake(
        type="NORMAL",
        margin=margin,
        use_selected_to_active=False,
        normal_space="TANGENT",
    )
    bake_end_time = time.time()
    bake_duration = int(bake_end_time - bake_start_time)
    debug_print(f"    ✔️ Normal: {bake_duration} seconds")

    return target_image


############################
# Helper functions
############################


def _make_shader_nodes(
    channels: list,
    shader_state: NodeGraphState,
    principled_tree: bpy.types.NodeTree,
    principled_bsdf: bpy.types.Node,
    separate_nodes: dict,
    target_node: bpy.types.Node,
    scalar: bool,
    debug_print,
) -> None:
    """
    Connect channels to target node (Combine Color or Emission).

    Args:
        channels: List of channel codes (e.g., ['cr', 'cg', 'cb'])
        shader_state: Node graph state tracker
        principled_tree: The node tree containing the nodes
        principled_bsdf: The Principled BSDF node
        separate_nodes: Dict mapping socket_name -> Separate Color node
        target_node: The target node to connect to (Combine Color or Emission)
        scalar: If True, the channel is not part of a Color socket. False, the channel represents part of a Color socket.
        debug_print: Debug print function
    """

    for i, channel in enumerate(channels):
        socket_mapping = DTP_SOCKET_MAP.get(channel)
        if not socket_mapping:
            debug_print(f"Could not resolve channel: {channel}")
            continue

        if scalar:
            # For scalar (single channel), always use 'Color' input
            input_name = "Color"
        else:
            # For RGB channels, use Red/Green/Blue inputs
            input_name = ["Red", "Green", "Blue"][i]

        # Handle constant values (0, 1) and unused (xx)
        # Note: 'xx' (unused) should only appear in alpha position and typically
        # gets stripped from the format string before reaching the baker.
        # If it somehow gets here, treat as 0.0 for safety.
        if socket_mapping in ("__CONSTANT_0__", "__UNUSED__"):
            if scalar:
                target_node.inputs[input_name].default_value = (0.0, 0.0, 0.0, 1.0)
            else:
                target_node.inputs[input_name].default_value = 0.0
            continue
        elif socket_mapping == "__CONSTANT_1__":
            if scalar:
                target_node.inputs[input_name].default_value = (1.0, 1.0, 1.0, 1.0)
            else:
                target_node.inputs[input_name].default_value = 1.0
            continue

        if isinstance(socket_mapping, tuple):
            # Color based channel (cr, cg, cb, er, eg, eb, etc.)
            socket_name, channel_index = socket_mapping
            socket = principled_bsdf.inputs.get(socket_name)

            # Special handling for emission channels - check emission strength
            # This check is here because Principled BSDF default emission to white.
            # Try to guess if it's unused, and set it to black.
            if socket_name == "Emission Color":
                # Get emission strength socket
                emission_strength_socket = principled_bsdf.inputs.get(
                    "Emission Strength"
                )
                if emission_strength_socket and not emission_strength_socket.is_linked:
                    strength_value = emission_strength_socket.default_value
                    if strength_value <= 0.0:
                        # Emission is unused, set black value directly on Combine Color
                        debug_print(
                            f"🔧 Emission strength <= 0, using black for channel {channel}"
                        )
                        # Set black value directly to target node
                        if scalar:
                            # For scalar, convert to RGB color
                            target_node.inputs[input_name].default_value = (
                                0.0,
                                0.0,
                                0.0,
                                1.0,
                            )
                        else:
                            # For RGB, use single value
                            target_node.inputs[input_name].default_value = 0.0
                        continue

            if socket and socket.is_linked:
                # Connect from separate
                separate_rgb = separate_nodes[socket_name]
                channel_names = ["Red", "Green", "Blue"]
                if scalar:
                    # For scalar, this shouldn't happen - scalar channels are not color-based
                    debug_print(
                        f"ERROR: Scalar channel {channel} should not be color-based"
                    )
                    continue
                else:
                    # For RGB, connect single channel
                    target_node.inputs[input_name].default_value = separate_rgb.outputs[
                        channel_names[channel_index]
                    ].default_value
                    shader_state.connect_sockets(
                        principled_tree,
                        separate_rgb,
                        channel_names[channel_index],
                        target_node,
                        input_name,
                        f"channel {channel} to {input_name}",
                    )
            else:
                # Not socketed, copy value directly
                if hasattr(socket, "default_value") and hasattr(
                    socket.default_value, "__getitem__"
                ):
                    # It's a color array, extract the specific channel
                    if scalar:
                        # For scalar, this shouldn't happen - scalar channels are not color-based
                        debug_print(
                            f"ERROR: Scalar channel {channel} should not be color-based"
                        )
                        continue
                    else:
                        # For RGB, use single channel value
                        target_node.inputs[input_name].default_value = (
                            socket.default_value[channel_index]
                        )
                else:
                    # It's already a single float value
                    if scalar:
                        # For scalar, convert to RGB color
                        target_node.inputs[input_name].default_value = (
                            socket.default_value,
                            socket.default_value,
                            socket.default_value,
                            1.0,
                        )
                    else:
                        # For RGB, use single value
                        target_node.inputs[input_name].default_value = (
                            socket.default_value
                        )
        else:
            # Not color based (me, sp, ro, al, etc.)
            socket_name = socket_mapping
            socket = principled_bsdf.inputs.get(socket_name)

            if socket and socket.is_linked:
                # Connect from socket
                from_socket = socket.links[0].from_socket
                # Don't set default_value when socket is linked - just connect
                shader_state.connect_sockets(
                    principled_tree,
                    from_socket.node,
                    from_socket.name,
                    target_node,
                    input_name,
                    f"channel {channel} to {input_name}",
                )
            else:
                # Not socketed, copy value directly
                if scalar:
                    # For scalar, convert single value to RGB color
                    target_node.inputs[input_name].default_value = (
                        socket.default_value,
                        socket.default_value,
                        socket.default_value,
                        1.0,
                    )
                else:
                    # For RGB, use single value
                    target_node.inputs[input_name].default_value = socket.default_value


def _pack_rgba_images(
    material: bpy.types.Material,
    dtp_format: str,
    rgb_image: bpy.types.Image,
    alpha_image: bpy.types.Image,
    resolution: Tuple[int, int],
    debug_print,
) -> Optional[bpy.types.Image]:
    """
    Pack RGB and Alpha images together.

    Args:
        material: The material (for naming)
        dtp_format: DTP format string
        rgb_image: RGB image
        alpha_image: Alpha image
        resolution: Target resolution for both images
        debug_print: Debug print function

    Returns:
        Packed RGBA image or None if failed
    """
    debug_print("📦 Packing RGB + A")

    # Convert images to numpy arrays
    rgb_array = _image_to_np(rgb_image)
    alpha_array = _image_to_np(alpha_image)

    # Both images should already be at the same resolution, but assert
    if (
        rgb_image.size[0] != alpha_image.size[0]
        or rgb_image.size[1] != alpha_image.size[1]
    ):
        raise ValueError(
            f"RGB and Alpha images have different sizes: {rgb_image.size[0]}x{rgb_image.size[1]} vs {alpha_image.size[0]}x{alpha_image.size[1]}"
        )

    # Create RGBA array
    rgba_array = rgb_array.copy()
    rgba_array[:, :, 3] = alpha_array[:, :, 0]  # Use R channel as alpha

    # Create final RGBA image
    final_image = bpy.data.images.new(
        name=f"bake_{material.name}_{dtp_format}",
        width=resolution[0],
        height=resolution[1],
        alpha=True,
        float_buffer=False,
    )

    # Copy numpy array to image
    _np_to_image_pixels(final_image, rgba_array)

    return final_image


def _parse_format_string(dtp_format: str) -> list:
    """
    Parse a DTP format string into a list of channels using DTP and SOCKET_MAP.

    Args:
        dtp_format: Format string like "me-sp-ro", "rgba", "ng-ng-ng-nx"

    Returns:
        List of channel codes like ['me', 'sp', 'ro'] or ['cr', 'cg', 'cb', 'al']
    """
    dtp_format = dtp_format.strip().lower()

    # Check if it's a single alias - use DTP's expansion
    if is_alias(dtp_format):
        return expand_alias(dtp_format)

    # Use DTP's channel validation
    if not is_flag_supported(dtp_format):
        raise ValueError(f"Unsupported DTP format: {dtp_format}")

    # Split by hyphens for individual channels
    channels = dtp_format.split("-")

    # Additional validation: ensure all channels are in SOCKET_MAP (baker-specific)
    for channel in channels:
        if channel not in DTP_SOCKET_MAP:
            raise ValueError(
                f"Channel '{channel}' not supported by baker (missing from SOCKET_MAP)"
            )

    return channels


def _get_bake_type_for_channels(channels: list) -> str:
    """Determine the appropriate bake type based on parsed channels."""
    # Check if this is a normal map alias (expanded to individual channels)
    if channels == ["nx", "ng"] or channels == ["nx", "nd"]:
        return "NORMAL"
    # Check if this contains only normal map channels
    elif all(channel in ["nx", "ng", "nd"] for channel in channels):
        return "NORMAL"
    else:
        return "EMIT"


def _optimize_baked_image(
    image: bpy.types.Image,
    obj: bpy.types.Object,
    max_resolution: Optional[Tuple[int, int]] = None,
) -> bpy.types.Image:
    """
    Optimize a baked image using mipmap analysis to find minimum safe resolution.

    Args:
        image: The baked image to optimize
        obj: Object for mipmap analysis
        max_resolution: Optional maximum resolution cap (width, height)

    Returns:
        Optimized image (may be the same image if no optimization needed)
    """

    def debug_print(*msgs):
        print("        ", *msgs)
        return

    if not obj or obj.type != "MESH":
        return image

    try:
        start_time = time.time()
        mip_results = analyze_mip_stats(obj, image)

        if mip_results and mip_results["min_safe_resolution"]:
            optimal_size = mip_results["min_safe_resolution"]
            current_size = (image.size[0], image.size[1])

            # Apply max_resolution cap if provided
            if max_resolution:
                max_width, max_height = max_resolution
                optimal_size = (
                    min(optimal_size[0], max_width),
                    min(optimal_size[1], max_height),
                )

            if optimal_size != current_size:
                debug_print(
                    f"🔍 Optimizing from {current_size[0]}x{current_size[1]} to {optimal_size[0]}x{optimal_size[1]}"
                )
                optimized_output = resize_image_to_size(
                    image, optimal_size[0], optimal_size[1]
                )
                optimized_output.name = f"optimized_{image.name}"
                bpy.data.images.remove(image)
                image = optimized_output
                debug_print(f"✅ Optimization complete")

        analysis_time = int(time.time() - start_time)
        debug_print(f"🔍 Optimization analysis finished in {analysis_time} s")

    except Exception as e:
        debug_print(f"⚠️ Packed texture optimization failed: {e}")

    return image


def create_default_texture(
    width: int, height: int, color: Tuple[float, float, float, float]
) -> bpy.types.Image:
    """
    Create a solid color texture in Blender's image memory.

    Args:
        width: Texture width in pixels
        height: Texture height in pixels
        color: RGBA color as tuple (values 0.0-1.0)

    Returns:
        Blender Image datablock with solid color
    """
    # Create a new image in Blender
    img = bpy.data.images.new(
        name=f"default_{width}x{height}", width=width, height=height, alpha=True
    )

    # Fill with the specified color
    pixels = [color[i % 4] for i in range(width * height * 4)]
    img.pixels[:] = pixels
    img.update()

    return img


def _ensure_uv_map(obj: bpy.types.Object) -> bool:
    """
    Ensure the object has a UV map. Creates one if missing.

    Args:
        obj: The object to check/modify

    Returns:
        True if UV map exists or was created, False if failed
    """

    def debug_print(*msgs):
        print("        ", *msgs)
        return

    if obj.type != "MESH":
        return False

    mesh = obj.data

    # Check if UV map already exists
    if len(mesh.uv_layers) > 0:
        return True

    # Create a basic UV map using Smart UV Project
    try:
        # Store current mode
        current_mode = obj.mode

        # Enter edit mode
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")

        # Select all
        bpy.ops.mesh.select_all(action="SELECT")

        # Create UV unwrap
        bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.1)

        # Return to original mode
        bpy.ops.object.mode_set(mode=current_mode)

        return True
    except Exception as e:
        debug_print(f"ERROR: Failed to create UV map for {obj.name}: {e}")
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except:
            pass
        return False
