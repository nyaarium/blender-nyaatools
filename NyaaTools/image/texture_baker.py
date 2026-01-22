"""Texture baking utilities for rendering Blender material sockets to texture maps."""

import bpy
import time
from typing import Optional, Tuple, List, Dict

from .material_analyzer import detect_best_resolution, build_tree_stack
from .node_graph_state import NodeGraphState
from .dtp_format import is_flag_supported, expand_alias, is_alias
from ..uv.analyze_mip_stats import analyze_mip_stats
from .texture_utils import resize_image_to_size, _image_to_np, _np_to_image_pixels


def _get_bake_margin(resolution: Tuple[int, int]) -> int:
    """
    Calculate bake margin based on resolution.
    """
    width, height = resolution
    max_dimension = max(width, height)
    return max(16, int(max_dimension / 4))


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
    uv_layer_name: Optional[str] = None,
    image_type: str = "png",
) -> Optional[bpy.types.Image]:
    """
    Bake a material to a texture using DTP format specification.

    Replaces ALL Principled BSDFs with Emission nodes inline to preserve shader routing
    (Mix Shaders, face attributes, etc.). The Material Output is NOT modified.

    Args:
        dtp_format: DTP format string (e.g., "rgba", "normalgl", "me-sp-ro")
        obj: The mesh object to bake from
        material: The material to bake
        resolution: Fixed resolution (width, height). If None, auto-detect.
        max_resolution: Maximum resolution cap (width, height)
        uv_layer_name: Specific UV layer to use. If None, uses first UV layer.
        image_type: Output image format ("png" or "exr"). Affects float_buffer setting.

    Returns:
        The baked image, or None if baking failed
    """

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

    # Bake by replacing all Principled BSDFs inline
    return _bake_with_all_principled_replaced(
        dtp_format=dtp_format,
        obj=obj,
        material=material,
        channels=channels,
        bake_type=bake_type,
        resolution=resolution,
        max_resolution=max_resolution,
        uv_layer_name=uv_layer_name,
        image_type=image_type,
        debug_print=debug_print,
    )


def _find_all_principled_bsdfs(
    node_tree: bpy.types.NodeTree,
    debug_print,
    visited: set = None,
) -> List[Dict]:
    """
    Find all Principled BSDF nodes in a tree, including inside node groups.

    Returns a list of dicts with:
        - "node": The Principled BSDF node
        - "tree": The NodeTree containing the node

    Args:
        node_tree: The node tree to search
        debug_print: Debug print function
        visited: Set of visited tree names (to prevent infinite recursion)

    Returns:
        List of {"node": Node, "tree": NodeTree} dicts
    """
    if visited is None:
        visited = set()

    # Prevent infinite recursion from circular group references
    if node_tree.name in visited:
        return []
    visited.add(node_tree.name)

    results = []

    for node in node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            results.append({"node": node, "tree": node_tree})
        elif node.type == "GROUP" and node.node_tree:
            # Recurse into group
            group_results = _find_all_principled_bsdfs(
                node.node_tree, debug_print, visited
            )
            results.extend(group_results)

    return results


def _bake_with_all_principled_replaced(
    dtp_format: str,
    obj: bpy.types.Object,
    material: bpy.types.Material,
    channels: list,
    bake_type: str,
    resolution: Optional[Tuple[int, int]],
    max_resolution: Optional[Tuple[int, int]],
    uv_layer_name: Optional[str],
    image_type: str,
    debug_print,
) -> Optional[bpy.types.Image]:
    """
    Internal: Bake by replacing ALL Principled BSDFs with Emission nodes inline.

    This preserves shader routing (Mix Shaders, face attributes, etc.) and does NOT
    modify the Material Output node.

    Args:
        dtp_format: DTP format string
        obj: The mesh object to bake from
        material: The material to bake
        channels: Parsed channel list
        bake_type: "EMIT" or "NORMAL"
        resolution: Fixed resolution (width, height)
        max_resolution: Maximum resolution cap
        uv_layer_name: Specific UV layer to use
        image_type: Output image format
        debug_print: Debug print function

    Returns:
        The baked image, or None if baking failed
    """
    debug_print(
        f"[replace_all_principled] Baking {dtp_format} with all Principled BSDFs replaced inline"
    )

    if not material:
        debug_print("  ERROR: Material is None")
        return None

    if not material.use_nodes:
        debug_print("  ERROR: Material has use_nodes=False")
        return None

    tree = material.node_tree
    if not tree:
        debug_print("  ERROR: Material.node_tree is None")
        return None

    nodes = tree.nodes
    links = tree.links

    # Create shader state tracker for safe restoration
    shader_state = NodeGraphState(material, tree, tree)

    debug_print(f"  Material '{material.name}': {len(nodes)} total nodes")

    # Find all Principled BSDF nodes (including in node groups)
    principled_infos = _find_all_principled_bsdfs(tree, debug_print)
    if not principled_infos:
        debug_print("  ERROR: No Principled BSDF nodes found")
        # List all node types for debugging
        all_types = sorted(set(n.type for n in nodes))
        debug_print(f"  Available node types: {all_types}")
        return None

    debug_print(f"  Found {len(principled_infos)} Principled BSDF node(s)")

    tree_stack = build_tree_stack(material)

    # Detect resolution from all principled's connected textures if not specified
    detected_resolution = None
    if resolution is None:
        all_resolutions = []

        for info in principled_infos:
            principled = info["node"]

            # Helper to check socket
            def check_socket(socket_name):
                socket = principled.inputs.get(socket_name)
                if socket and socket.is_linked:
                    res = detect_best_resolution(socket, tree_stack)
                    if res != (512, 512):  # Only keep non-default results
                        all_resolutions.append(res)

            if bake_type == "NORMAL":
                check_socket("Normal")
            else:
                # Check standard heavy sockets
                check_socket("Base Color")
                check_socket("Emission Color")

                # Check sockets specific to this DTP format
                for channel in channels:
                    socket_mapping = DTP_SOCKET_MAP.get(channel)
                    if isinstance(socket_mapping, str) and socket_mapping not in (
                        "__CONSTANT_0__",
                        "__CONSTANT_1__",
                        "__UNUSED__",
                    ):
                        check_socket(socket_mapping)
                    elif isinstance(socket_mapping, tuple):
                        socket_name, _ = socket_mapping
                        check_socket(socket_name)

        if all_resolutions:
            # Find max resolution
            max_w = max(r[0] for r in all_resolutions)
            max_h = max(r[1] for r in all_resolutions)
            detected_resolution = (max_w, max_h)
            debug_print(
                f"  Auto-detected resolution: {detected_resolution} (from {len(all_resolutions)} sources)"
            )
        else:
            detected_resolution = (512, 512)
            debug_print("  Auto-detected resolution: (512, 512) (fallback)")

    # Determine final resolution
    final_resolution = resolution or detected_resolution or (512, 512)
    if max_resolution:
        max_width, max_height = max_resolution
        final_resolution = (
            min(final_resolution[0], max_width),
            min(final_resolution[1], max_height),
        )
    debug_print(f"  Final resolution: {final_resolution}")

    # Check if alpha is in use (4th channel that's not 'xx')
    has_alpha = len(channels) == 4 and channels[3] != "xx"

    # Store RGB and Alpha emissions for 2-stage bake if needed
    rgb_emissions = []
    alpha_emissions = []

    # Replace each Principled BSDF with Emission inline (in their respective trees)
    # Use shader_state to track changes for restoration
    for info in principled_infos:
        principled = info["node"]
        principled_tree = info["tree"]

        if bake_type == "NORMAL":
            # For NORMAL baking, replace with temp Principled BSDF that only has Normal connected
            rgb_emission, alpha_emission = _replace_principled_for_normal_bake(
                shader_state,
                principled_tree,
                principled,
                debug_print,
            )
        else:
            # For EMIT baking, replace with Emission nodes
            rgb_emission, alpha_emission = _replace_principled_with_emission_tracked(
                shader_state,
                principled_tree,
                principled,
                channels,
                has_alpha,
                debug_print,
            )

        if rgb_emission:
            rgb_emissions.append((rgb_emission, principled_tree))
        if has_alpha and alpha_emission:
            alpha_emissions.append((alpha_emission, principled_tree))

    # Ensure UV map exists
    if not _ensure_uv_map(obj):
        debug_print(f"Warning: Could not ensure UV map for object {obj.name}")
        shader_state.restore()
        return None

    # Set up render settings
    scene = bpy.context.scene
    original_engine = scene.render.engine
    original_samples = scene.cycles.samples if hasattr(scene, "cycles") else None
    original_film_transparent = scene.render.film_transparent

    scene.render.engine = "CYCLES"
    scene.render.film_transparent = False
    if hasattr(scene, "cycles"):
        scene.cycles.samples = 1

    # Setup object selection
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Ensure OBJECT mode
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    # Set UV layer
    mesh_data = obj.data
    if mesh_data.uv_layers:
        target_uv_name = uv_layer_name if uv_layer_name else mesh_data.uv_layers[0].name
        target_uv = mesh_data.uv_layers.get(target_uv_name)
        if target_uv:
            mesh_data.uv_layers.active = target_uv
            debug_print(f"  Using UV layer: {target_uv_name}")
        else:
            debug_print(f"  ⚠️ UV layer '{target_uv_name}' not found, using first")
            mesh_data.uv_layers.active = mesh_data.uv_layers[0]

    # Create bake target image
    use_float = image_type == "exr"
    is_utility = _is_utility_map(channels)

    bake_image = None

    try:
        if bake_type == "NORMAL":
            # Normal baking
            bake_image = _execute_normal_bake(
                material,
                dtp_format,
                shader_state,
                tree,
                final_resolution,
                mesh_data,
                uv_layer_name,
                channels,
                use_float,
                debug_print,
            )
        elif has_alpha:
            # 2-stage bake: RGB first, then Alpha, then repack
            debug_print(f"  Alpha detected: doing 2-stage bake (RGB + Alpha)")
            bake_image = _execute_two_stage_bake(
                material,
                dtp_format,
                shader_state,
                tree,
                final_resolution,
                rgb_emissions,
                alpha_emissions,
                use_float,
                is_utility,
                debug_print,
            )
        else:
            # Regular single bake (RGB only)
            bake_image = _execute_emit_bake(
                material,
                dtp_format,
                shader_state,
                tree,
                final_resolution,
                use_float,
                is_utility,
                debug_print,
            )

        # Apply optimization if user didn't specify resolution
        if bake_image and resolution is None:
            bake_image = _optimize_baked_image(bake_image, obj, max_resolution)

    except Exception as e:
        debug_print(f"  Bake operation failed: {e}")
        import traceback

        traceback.print_exc()
        bake_image = None

    finally:
        # Restore shader state (removes temp nodes, restores connections)
        shader_state.restore()

        # Restore render settings
        scene.render.engine = original_engine
        scene.render.film_transparent = original_film_transparent
        if original_samples is not None and hasattr(scene, "cycles"):
            scene.cycles.samples = original_samples

    return bake_image


def _replace_principled_for_normal_bake(
    shader_state: NodeGraphState,
    principled_tree: bpy.types.NodeTree,
    principled: bpy.types.ShaderNode,
    debug_print,
) -> Tuple[Optional[bpy.types.Node], None]:
    """
    Replace a Principled BSDF with a temporary Principled BSDF that only has Normal connected.

    This is used for NORMAL bake type where we need the Principled BSDF for proper
    normal map baking, but we want to isolate just the normal input.

    Args:
        shader_state: NodeGraphState tracker for restoration
        principled_tree: The node tree containing the Principled BSDF
        principled: The Principled BSDF to bypass
        debug_print: Debug print function

    Returns:
        Tuple of (temp principled node, None). Alpha is always None for normals.
    """
    links = principled_tree.links

    # Create temporary Principled BSDF (tracked as temporary)
    temp_principled = shader_state.add_node(principled_tree, "ShaderNodeBsdfPrincipled")
    temp_principled.location = (principled.location.x + 200, principled.location.y)

    # Connect normal map from original Principled to temp Principled
    normal_socket = principled.inputs.get("Normal")
    if normal_socket and normal_socket.is_linked:
        from_socket = normal_socket.links[0].from_socket
        links.new(from_socket, temp_principled.inputs["Normal"])

    # Capture where Principled BSDF outputs connect to
    reconnect_targets = []
    for output in principled.outputs:
        if output.name == "BSDF":
            for link in output.links:
                reconnect_targets.append(
                    {
                        "node": link.to_node,
                        "socket": link.to_socket,
                        "socket_name": link.to_socket.name,
                    }
                )

    # Disconnect original Principled's BSDF output and connect temp Principled
    for target in reconnect_targets:
        shader_state.detach_socket(target["socket"])

    # Connect temp Principled to all targets
    for target in reconnect_targets:
        shader_state.connect_sockets(
            principled_tree,
            temp_principled,
            "BSDF",
            target["node"],
            target["socket_name"],
            f"Normal bake bypass for {principled.name}",
        )

    debug_print(f"    {principled.name}: Normal → temp Principled → inline bypass")

    return temp_principled, None


def _replace_principled_with_emission_tracked(
    shader_state: NodeGraphState,
    principled_tree: bpy.types.NodeTree,
    principled: bpy.types.ShaderNode,
    channels: list,
    has_alpha: bool,
    debug_print,
) -> Tuple[Optional[bpy.types.Node], Optional[bpy.types.Node]]:
    """
    Replace a single Principled BSDF with an Emission node inline, tracking changes for restoration.

    Uses NodeGraphState to track all modifications so they can be restored after baking.
    Does NOT delete the Principled BSDF - just bypasses it inline.

    Args:
        shader_state: NodeGraphState tracker for restoration
        principled_tree: The node tree containing the Principled BSDF
        principled: The Principled BSDF to bypass
        channels: Parsed DTP channels
        has_alpha: Whether alpha channel is in use
        debug_print: Debug print function

    Returns:
        Tuple of (RGB emission node, Alpha emission node). Alpha will be None if has_alpha is False.
    """
    links = principled_tree.links

    # Create RGB Emission node (tracked as temporary)
    rgb_emission = shader_state.add_node(principled_tree, "ShaderNodeEmission")
    rgb_emission.location = (principled.location.x + 200, principled.location.y)

    # Create Combine Color node for RGB channels (tracked as temporary)
    combine = shader_state.add_node(principled_tree, "ShaderNodeCombineColor")
    combine.mode = "RGB"
    combine.location = (principled.location.x + 50, principled.location.y)

    # Connect Combine Color -> RGB Emission
    links.new(combine.outputs["Color"], rgb_emission.inputs["Color"])

    # Create Separate Color nodes for all color-based sockets that are linked
    separate_nodes = {}
    for channel in channels[:3]:  # Only RGB channels
        socket_mapping = DTP_SOCKET_MAP.get(channel)
        if isinstance(socket_mapping, tuple):
            sock_name, _ = socket_mapping
            if sock_name not in separate_nodes:
                sock = principled.inputs.get(sock_name)
                if sock and sock.is_linked:
                    # Create Separate Color node (tracked as temporary)
                    sep = shader_state.add_node(
                        principled_tree, "ShaderNodeSeparateColor"
                    )
                    sep.mode = "RGB"
                    sep.location = (
                        principled.location.x - 100,
                        principled.location.y - len(separate_nodes) * 100,
                    )

                    # Connect from the same source as Principled's input
                    from_socket = sock.links[0].from_socket
                    links.new(from_socket, sep.inputs["Color"])
                    separate_nodes[sock_name] = sep
                    debug_print(f"    Created Separate Color for {sock_name}")

    # Wire RGB channels to Combine Color
    combine_inputs = ["Red", "Green", "Blue"]
    for i, channel in enumerate(channels[:3]):
        _wire_channel_to_combine_tracked(
            principled_tree,
            principled,
            separate_nodes,
            combine,
            combine_inputs[i],
            channel,
            debug_print,
        )

    debug_print(
        f"    {principled.name}: [{'-'.join(channels[:3])}] → Combine → Emission"
    )

    # Capture where Principled BSDF outputs connect to
    reconnect_targets = []
    for output in principled.outputs:
        if output.name == "BSDF":
            for link in output.links:
                to_node = link.to_node
                to_socket = link.to_socket
                # For Mix Shader, capture the input index
                input_index = None
                if to_node.type == "MIX_SHADER":
                    for idx, inp in enumerate(to_node.inputs):
                        if inp == to_socket:
                            input_index = idx
                            break

                reconnect_targets.append(
                    {
                        "node": to_node,
                        "socket": to_socket,
                        "socket_name": to_socket.name,
                        "input_index": input_index,
                    }
                )

    # Disconnect original Principled's BSDF output by detaching target sockets
    for target in reconnect_targets:
        shader_state.detach_socket(target["socket"])

    # Connect Emission to all targets (inline bypass)
    for target in reconnect_targets:
        to_node = target["node"]
        to_socket_name = target["socket_name"]
        input_index = target["input_index"]

        if to_node.type == "MIX_SHADER" and input_index is not None:
            # Connect to specific input index for Mix Shader
            target_socket = to_node.inputs[input_index]
            emission_output = rgb_emission.outputs.get("Emission")
            if emission_output and target_socket:
                principled_tree.links.new(emission_output, target_socket)
        else:
            # Use shader_state.connect_sockets for other node types
            shader_state.connect_sockets(
                principled_tree,
                rgb_emission,
                "Emission",
                to_node,
                to_socket_name,
                f"RGB emission bypass for {principled.name}",
            )

    # Create Alpha emission node if alpha is in use
    alpha_emission = None
    if has_alpha and len(channels) == 4:
        alpha_channel = channels[3]
        alpha_emission = shader_state.add_node(principled_tree, "ShaderNodeEmission")
        alpha_emission.location = (
            principled.location.x + 200,
            principled.location.y - 150,
        )

        # Wire alpha channel to Alpha emission
        socket_mapping = DTP_SOCKET_MAP.get(alpha_channel)
        if socket_mapping and socket_mapping == "Alpha":
            alpha_socket = principled.inputs.get("Alpha")
            if alpha_socket:
                if alpha_socket.is_linked:
                    from_socket = alpha_socket.links[0].from_socket
                    # Convert scalar to RGB (grayscale) using Combine RGB
                    combine_alpha = shader_state.add_node(
                        principled_tree, "ShaderNodeCombineColor"
                    )
                    combine_alpha.mode = "RGB"
                    combine_alpha.location = (
                        alpha_emission.location.x - 150,
                        alpha_emission.location.y,
                    )

                    # Connect scalar to all RGB inputs
                    links.new(from_socket, combine_alpha.inputs["Red"])
                    links.new(from_socket, combine_alpha.inputs["Green"])
                    links.new(from_socket, combine_alpha.inputs["Blue"])

                    # Connect Combine RGB to Emission
                    links.new(
                        combine_alpha.outputs["Color"], alpha_emission.inputs["Color"]
                    )
                else:
                    # Use default value as grayscale
                    alpha_val = alpha_socket.default_value
                    alpha_emission.inputs["Color"].default_value = (
                        alpha_val,
                        alpha_val,
                        alpha_val,
                        1.0,
                    )

    return rgb_emission, alpha_emission


def _wire_channel_to_combine_tracked(
    principled_tree: bpy.types.NodeTree,
    principled: bpy.types.ShaderNode,
    separate_nodes: dict,
    combine: bpy.types.ShaderNode,
    combine_input: str,
    channel: str,
    debug_print,
) -> None:
    """
    Wire a single DTP channel to a Combine Color input.

    Args:
        principled_tree: The node tree
        principled: Source Principled BSDF
        separate_nodes: Dict mapping socket_name -> Separate Color node
        combine: Target Combine Color node
        combine_input: "Red", "Green", or "Blue"
        channel: DTP channel code
        debug_print: Debug function
    """
    links = principled_tree.links
    socket_mapping = DTP_SOCKET_MAP.get(channel)

    if not socket_mapping:
        debug_print(f"    Unknown channel: {channel}")
        return

    # Handle constants
    if socket_mapping in ("__CONSTANT_0__", "__UNUSED__"):
        combine.inputs[combine_input].default_value = 0.0
        return
    elif socket_mapping == "__CONSTANT_1__":
        combine.inputs[combine_input].default_value = 1.0
        return

    if isinstance(socket_mapping, tuple):
        # Color-based channel (cr, cg, cb, er, eg, eb, etc.)
        socket_name, channel_idx = socket_mapping
        source_socket = principled.inputs.get(socket_name)

        # Special handling for emission - check if strength is 0
        if socket_name == "Emission Color":
            emission_strength = principled.inputs.get("Emission Strength")
            if emission_strength and not emission_strength.is_linked:
                if emission_strength.default_value <= 0.0:
                    combine.inputs[combine_input].default_value = 0.0
                    return

        if source_socket and source_socket.is_linked:
            # Use Separate Color node
            if socket_name in separate_nodes:
                sep = separate_nodes[socket_name]
                sep_outputs = ["Red", "Green", "Blue"]
                links.new(
                    sep.outputs[sep_outputs[channel_idx]], combine.inputs[combine_input]
                )
        else:
            # Use default value
            if source_socket and hasattr(source_socket, "default_value"):
                default_val = source_socket.default_value
                if hasattr(default_val, "__getitem__"):
                    combine.inputs[combine_input].default_value = default_val[
                        channel_idx
                    ]
    else:
        # Scalar socket (me, sp, ro, al, etc.)
        socket_name = socket_mapping
        source_socket = principled.inputs.get(socket_name)

        if source_socket:
            if source_socket.is_linked:
                from_socket = source_socket.links[0].from_socket
                links.new(from_socket, combine.inputs[combine_input])
            else:
                combine.inputs[combine_input].default_value = (
                    source_socket.default_value
                )


def _execute_normal_bake(
    material: bpy.types.Material,
    dtp_format: str,
    shader_state: NodeGraphState,
    tree: bpy.types.NodeTree,
    resolution: Tuple[int, int],
    mesh_data: bpy.types.Mesh,
    uv_layer_name: Optional[str],
    channels: list,
    use_float: bool,
    debug_print,
) -> Optional[bpy.types.Image]:
    """
    Execute a NORMAL bake.

    Args:
        material: The material being baked
        dtp_format: DTP format string
        shader_state: NodeGraphState tracker
        tree: Root node tree
        resolution: Bake resolution
        mesh_data: Mesh data for UV layer
        uv_layer_name: UV layer name
        channels: Parsed channel list
        use_float: Whether to use float buffer
        debug_print: Debug print function

    Returns:
        Baked image or None
    """
    # Check if there's a valid 4th channel (not 'xx' unused)
    has_alpha = len(channels) == 4 and channels[3] != "xx"

    # Create target image
    target_image = bpy.data.images.new(
        name=f"bake_{material.name}_{dtp_format}",
        width=resolution[0],
        height=resolution[1],
        alpha=has_alpha,
        float_buffer=use_float,
    )
    target_image.colorspace_settings.name = "Non-Color"

    # Create image texture node in ROOT tree
    img_node = shader_state.add_node(tree, "ShaderNodeTexImage")
    img_node.image = target_image
    img_node.select = True
    tree.nodes.active = img_node

    # Add UVMap node and connect to Image Texture
    target_uv_name = (
        uv_layer_name
        if uv_layer_name
        else (mesh_data.uv_layers[0].name if mesh_data.uv_layers else None)
    )
    if target_uv_name:
        uv_node = shader_state.add_node(tree, "ShaderNodeUVMap")
        uv_node.uv_map = target_uv_name
        uv_node.location = (img_node.location.x - 200, img_node.location.y)
        tree.links.new(uv_node.outputs["UV"], img_node.inputs["Vector"])

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


def _execute_emit_bake(
    material: bpy.types.Material,
    dtp_format: str,
    shader_state: NodeGraphState,
    tree: bpy.types.NodeTree,
    resolution: Tuple[int, int],
    use_float: bool,
    is_utility: bool,
    debug_print,
) -> Optional[bpy.types.Image]:
    """
    Execute an EMIT bake (single stage, no alpha).

    Args:
        material: The material being baked
        dtp_format: DTP format string
        shader_state: NodeGraphState tracker
        tree: Root node tree
        resolution: Bake resolution
        use_float: Whether to use float buffer
        is_utility: Whether this is utility map data
        debug_print: Debug print function

    Returns:
        Baked image or None
    """
    # Create bake target image
    bake_image = bpy.data.images.new(
        name=f"bake_{material.name}_{dtp_format}",
        width=resolution[0],
        height=resolution[1],
        alpha=False,
        float_buffer=use_float,
    )

    # Set colorspace
    if is_utility:
        bake_image.colorspace_settings.name = "Non-Color"

    # Create image texture node for bake target
    img_node = shader_state.add_node(tree, "ShaderNodeTexImage")
    img_node.image = bake_image
    img_node.select = True
    tree.nodes.active = img_node

    # Execute bake
    debug_print(f"🍞 Baking EMIT at {resolution[0]}x{resolution[1]}")

    try:
        margin = _get_bake_margin(resolution)
        bake_start_time = time.time()
        bpy.ops.object.bake(
            type="EMIT",
            use_clear=True,
            margin=margin,
            margin_type="EXTEND",
        )
        bake_end_time = time.time()
        bake_duration = int(bake_end_time - bake_start_time)
        debug_print(f"    ✔️ RGB: {bake_duration} seconds")

    except Exception as e:
        debug_print(f"  Bake failed: {e}")
        bpy.data.images.remove(bake_image)
        return None

    return bake_image


def _execute_two_stage_bake(
    material: bpy.types.Material,
    dtp_format: str,
    shader_state: NodeGraphState,
    tree: bpy.types.NodeTree,
    resolution: Tuple[int, int],
    rgb_emissions: list,
    alpha_emissions: list,
    use_float: bool,
    is_utility: bool,
    debug_print,
) -> Optional[bpy.types.Image]:
    """
    Execute a 2-stage bake: RGB first, then Alpha, then repack.

    Args:
        material: The material being baked
        dtp_format: DTP format string
        shader_state: NodeGraphState tracker
        tree: Root node tree
        resolution: Bake resolution
        rgb_emissions: List of (rgb_emission_node, tree) tuples
        alpha_emissions: List of (alpha_emission_node, tree) tuples
        use_float: Whether to use float buffer
        is_utility: Whether this is utility map data
        debug_print: Debug print function

    Returns:
        Packed RGBA image or None
    """
    nodes = tree.nodes

    # Stage 1: Bake RGB
    rgb_image = bpy.data.images.new(
        name=f"bake_{material.name}_{dtp_format}_rgb",
        width=resolution[0],
        height=resolution[1],
        alpha=False,
        float_buffer=use_float,
    )

    if is_utility:
        rgb_image.colorspace_settings.name = "Non-Color"

    img_node = shader_state.add_node(tree, "ShaderNodeTexImage")
    img_node.image = rgb_image
    img_node.select = True
    nodes.active = img_node

    debug_print(f"🍞 Baking RGB at {resolution[0]}x{resolution[1]}...")
    try:
        margin = _get_bake_margin(resolution)
        bake_start_time = time.time()
        bpy.ops.object.bake(
            type="EMIT",
            use_clear=True,
            margin=margin,
            margin_type="EXTEND",
        )
        bake_end_time = time.time()
        rgb_duration = int(bake_end_time - bake_start_time)
        debug_print(f"    ✔️ RGB:   {rgb_duration} seconds")
    except Exception as e:
        debug_print(f"  RGB bake failed: {e}")
        bpy.data.images.remove(rgb_image)
        return None

    # Stage 2: Disconnect RGB emissions and connect Alpha emissions
    # Swap all RGB emissions with their corresponding Alpha emissions
    for (rgb_emission, rgb_tree), (alpha_emission, alpha_tree) in zip(
        rgb_emissions, alpha_emissions
    ):
        # Find what RGB emission is connected to
        rgb_output = rgb_emission.outputs.get("Emission")
        if rgb_output and rgb_output.links:
            for link in list(rgb_output.links):
                to_socket = link.to_socket
                # Disconnect RGB emission
                shader_state.detach_socket(to_socket)
                # Connect Alpha emission to the same target
                shader_state.connect_sockets(
                    alpha_tree,
                    alpha_emission,
                    "Emission",
                    to_socket.node,
                    to_socket.name,
                    "Alpha emission bypass",
                )

    # Stage 3: Bake Alpha
    alpha_image = bpy.data.images.new(
        name=f"bake_{material.name}_{dtp_format}_alpha",
        width=resolution[0],
        height=resolution[1],
        alpha=False,
        float_buffer=use_float,
    )

    if is_utility:
        alpha_image.colorspace_settings.name = "Non-Color"

    img_node.image = alpha_image

    debug_print(f"🍞 Baking Alpha at {resolution[0]}x{resolution[1]}...")
    try:
        margin = _get_bake_margin(resolution)
        bake_start_time = time.time()
        bpy.ops.object.bake(
            type="EMIT",
            use_clear=True,
            margin=margin,
            margin_type="EXTEND",
        )
        bake_end_time = time.time()
        alpha_duration = int(bake_end_time - bake_start_time)
        debug_print(f"    ✔️ Alpha: {alpha_duration} seconds")
    except Exception as e:
        debug_print(f"  Alpha bake failed: {e}")
        bpy.data.images.remove(rgb_image)
        bpy.data.images.remove(alpha_image)
        return None

    # Stage 4: Pack RGB + Alpha together
    debug_print("📦 Packing RGB + A")
    bake_image = _pack_rgba_images(
        material,
        dtp_format,
        rgb_image,
        alpha_image,
        resolution,
        use_float,
        is_utility,
        debug_print,
    )

    # Clean up intermediate images
    bpy.data.images.remove(rgb_image)
    bpy.data.images.remove(alpha_image)

    return bake_image


def _pack_rgba_images(
    material: bpy.types.Material,
    dtp_format: str,
    rgb_image: bpy.types.Image,
    alpha_image: bpy.types.Image,
    resolution: Tuple[int, int],
    use_float: bool,
    is_utility: bool,
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
        use_float: Whether to use float buffer for the final image
        is_utility: Whether this is utility map data (affects colorspace)
        debug_print: Debug print function

    Returns:
        Packed RGBA image or None if failed
    """
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
        float_buffer=use_float,
    )

    # Set colorspace: Non-Color for utility maps, sRGB for color data
    if is_utility:
        final_image.colorspace_settings.name = "Non-Color"

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


def _is_utility_map(channels: list) -> bool:
    """
    Determine if channels represent utility map data (non-color, scalar values).

    Utility maps are grayscale/scalar data like metallic, roughness, specular, etc.
    They should use Non-Color colorspace and don't contain RGB color channels.

    Args:
        channels: List of channel codes (e.g., ['me', 'sp', 'ro'])

    Returns:
        True if this is utility map data, False if it's color data
    """
    # Color channels that indicate this is color data
    color_channels = {"cr", "cg", "cb", "er", "eg", "eb", "lr", "lg", "lb"}

    # Normal channels are handled separately
    normal_channels = {"nx", "ng", "nd"}

    # Check if any channel is a color channel
    has_color = any(channel in color_channels for channel in channels)

    # Check if any channel is a normal channel
    has_normal = any(channel in normal_channels for channel in channels)

    # If it has color channels, it's not a utility map
    if has_color:
        return False

    # If it has normal channels, it's not a utility map (normals are handled separately)
    if has_normal:
        return False

    # Everything else (me, sp, ro, ao, he, es, sm, al, etc.) is utility data
    return True


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
