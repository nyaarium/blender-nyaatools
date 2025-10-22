"""Texture baking utilities for rendering Blender material sockets to texture maps."""

import bpy
import time
import traceback
from typing import Optional, Tuple

from .material_analyzer import find_principled_bsdf, find_largest_texture_resolution
from .node_graph_state import NodeGraphState
from .dtp_format import is_flag_supported, expand_alias, is_alias
from .uv.analyze_mip_stats import analyze_mip_stats
from .texture_utils import resize_image_to_size


# DTP channel mapping for sockets and texture baking
DTP_SOCKET_MAP = {
    # Direct sockets (grayscale/scalar values)
    'me': 'Metallic',
    'sp': 'Specular IOR Level', 
    'ro': 'Roughness',
    'al': 'Alpha',
    'ao': 'Ambient Occlusion',
    'he': 'Height',
    'es': 'Emission Strength',
    'sm': 'Roughness',  # Smoothness (inverted roughness)
    
    # RGB sockets (need Separate RGB for individual channels)
    'cr': ('Base Color', 0),      # R channel
    'cg': ('Base Color', 1),      # G channel  
    'cb': ('Base Color', 2),      # B channel
    'er': ('Emission Color', 0),  # R channel
    'eg': ('Emission Color', 1),  # G channel
    'eb': ('Emission Color', 2),  # B channel
    'nx': ('Normal', 0),          # R channel
    'ng': ('Normal', 1),          # G channel (OpenGL)
    'nd': ('Normal', 1),          # G channel (DirectX, inverted)
    
    # Linear color channels (for HDR workflows)
    'lr': ('Base Color', 0),      # Linear R channel
    'lg': ('Base Color', 1),      # Linear G channel
    'lb': ('Base Color', 2),      # Linear B channel
    
    # Special cases for normal maps (uses NORMAL bake type)
    'normalgl': 'Normal',
    'normaldx': 'Normal',
}


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
    channels = dtp_format.split('-')
    
    # Additional validation: ensure all channels are in SOCKET_MAP (baker-specific)
    for channel in channels:
        if channel not in DTP_SOCKET_MAP:
            raise ValueError(f"Channel '{channel}' not supported by baker (missing from SOCKET_MAP)")
    
    return channels


def _get_bake_type_for_channels(channels: list) -> str:
    """Determine the appropriate bake type based on parsed channels."""
    # Check if this is a normal map alias (expanded to individual channels)
    if channels == ['nx', 'ng'] or channels == ['nx', 'nd']:
        return 'NORMAL'
    # Check if this contains only normal map channels
    elif all(channel in ['nx', 'ng', 'nd'] for channel in channels):
        return 'NORMAL'
    else:
        return 'EMIT'


def _resolve_socket_source(material: bpy.types.Material, channel: str, state: NodeGraphState, principled_tree) -> Optional[object]:
    """
    Resolve a channel code to a socket or node output that can be connected to Combine RGB.
    
    Args:
        material: The material containing the Principled BSDF
        channel: Channel code like 'me', 'cr', 'ng', etc.
        state: NodeGraphState for safe node manipulation
        principled_tree: The node tree containing the Principled BSDF
    
    Returns:
        Socket or node output that can be connected to Combine RGB inputs, or None if not found
    """
    def debug_print(*msgs):
        print("      ", *msgs)
        return
    
    principled = find_principled_bsdf(material)
    if not principled:
        return None
    
    socket_mapping = DTP_SOCKET_MAP.get(channel)
    if not socket_mapping:
        return None
    
    # Handle special cases
    if channel in ['normalgl', 'normaldx']:
        # These are handled separately in the main function
        return None
    
    if isinstance(socket_mapping, str):
        # Handle direct socket connections (grayscale values)

        socket_name = socket_mapping
        socket = principled.inputs.get(socket_name)
        if not socket:
            return None
        
        # Special handling for smoothness (inverted roughness)
        if channel == 'sm':
            # Create a Math node to invert the roughness (1.0 - roughness)
            math_node = state.add_node(principled_tree, 'ShaderNodeMath')
            math_node.operation = 'SUBTRACT'
            math_node.inputs[0].default_value = 1.0  # First input: 1.0
            
            if socket.is_linked:
                # Connect roughness input to second input of math node
                from_socket = socket.links[0].from_socket
                state.connect_sockets(principled_tree, from_socket.node, from_socket.name, math_node, 'Value', f"roughness to math for {channel}")
            else:
                # Use default roughness value
                math_node.inputs[1].default_value = socket.default_value
            
            # Return the math node output (inverted roughness)
            return math_node.outputs['Value']
        
        # For unconnected sockets, return a special object that doesn't have node/name attributes
        if socket.is_linked:
            return socket.links[0].from_socket
        else:
            # Return a simple object with just the default value
            class UnconnectedSocket:
                def __init__(self, default_value):
                    self.default_value = default_value
            
            return UnconnectedSocket(socket.default_value)
    
    elif isinstance(socket_mapping, tuple):
        # Handle RGB channel extractions (need Separate RGB)

        socket_name, channel_index = socket_mapping
        socket = principled.inputs.get(socket_name)
        if not socket:
            debug_print(f"Socket not found: {socket_name}")
            return None
        
        # Special handling for emission channels - check emission strength
        # FIXME: This check is here because Principled BSDF default emission to white.
        #        Try to guess if it's unused, and set it to black.
        if socket_name == 'Emission Color':
            # Get emission strength socket
            emission_strength_socket = principled.inputs.get('Emission Strength')
            if emission_strength_socket and not emission_strength_socket.is_linked:
                strength_value = emission_strength_socket.default_value
                if strength_value <= 0.0:
                    # Emission is unused, return black for all channels
                    debug_print(f"🔧 Emission strength <= 0, using black for channel {channel}")
                    # Create a constant black value
                    black_node = state.add_node(principled_tree, 'ShaderNodeValue')
                    black_node.outputs[0].default_value = 0.0
                    return black_node.outputs[0]
        
        # Add Separate RGB node for non-emission channels
        separate_rgb = state.add_node(principled_tree, 'ShaderNodeSeparateRGB')
        
        if socket.is_linked:
            from_socket = socket.links[0].from_socket
            state.connect_sockets(principled_tree, from_socket.node, from_socket.name, separate_rgb, 'Image', f"separate RGB for {channel}")
        
        # Special handling for DirectX normal (nd) - invert the green channel
        if channel == 'nd':
            # Create a Math node to invert the green channel (1.0 - green)
            math_node = state.add_node(principled_tree, 'ShaderNodeMath')
            math_node.operation = 'SUBTRACT'
            math_node.inputs[0].default_value = 1.0  # First input: 1.0
            
            # Connect green channel to second input of math node
            state.connect_sockets(principled_tree, separate_rgb, 'G', math_node, 'Value', f"normal green to math for {channel}")
            
            # Return the math node output (inverted green)
            return math_node.outputs['Value']
        
        # Return the appropriate channel output for other channels
        channel_names = ['R', 'G', 'B']
        return separate_rgb.outputs.get(channel_names[channel_index])
    
    return None


def _build_emit_shader_graph(material: bpy.types.Material, channels: list, state: NodeGraphState, principled_tree, root_tree) -> Optional[object]:
    """
    Build shader graph for EMIT baking: channels → Combine RGB → Emission → Material Output.
    
    Args:
        material: The material containing the Principled BSDF
        channels: List of channel codes like ['me', 'sp', 'ro']
        state: NodeGraphState for safe node manipulation
        principled_tree: The node tree containing the Principled BSDF
        root_tree: The root material node tree
    
    Returns:
        Emission shader node that's connected to Material Output, or None if failed
    """
    def debug_print(*msgs):
        print("      ", *msgs)
        return
    
    if len(channels) > 3:
        debug_print(f"Too many channels for RGB: {len(channels)}")
        return None
    
    # Check for unused emission (strength <= 0) - only for pure emission formats
    emission_is_unused = False
    if any(channel in ['er', 'eg', 'eb'] for channel in channels):
        principled = find_principled_bsdf(material)
        if principled:
            emission_strength_socket = principled.inputs.get('Emission Strength')
            if emission_strength_socket and not emission_strength_socket.is_linked:
                strength_value = emission_strength_socket.default_value
                if strength_value <= 0.0:
                    emission_is_unused = True
                    debug_print(f"🔧 Emission strength <= 0, will create black image (unused)")
    
    # Add Combine RGB node
    combine_rgb = state.add_node(principled_tree, 'ShaderNodeCombineRGB')
    
    # Resolve and connect each channel
    for i, channel in enumerate(channels):
        source = _resolve_socket_source(material, channel, state, principled_tree)
        if not source:
            debug_print(f"Could not resolve channel: {channel}")
            continue
        
        # Connect to Combine RGB input
        input_name = ['R', 'G', 'B'][i]
        if hasattr(source, 'node') and hasattr(source, 'name'):
            # It's a node output - connect it
            state.connect_sockets(principled_tree, source.node, source.name, combine_rgb, input_name, f"channel {channel} to {input_name}")
        else:
            # It's an unconnected socket - create a Value node with the default value
            value_node = state.add_node(principled_tree, 'ShaderNodeValue')
            value_node.outputs[0].default_value = source.default_value
            state.connect_sockets(principled_tree, value_node, 'Value', combine_rgb, input_name, f"default {channel} to {input_name}")
    
    # Add Emission shader (with commented code stub for Diffuse BSDF alternative)
    emission_shader = state.add_node(principled_tree, 'ShaderNodeEmission')
    # Alternative: diffuse_shader = state.add_node(principled_tree, 'ShaderNodeBsdfDiffuse')
    
    # Connect Combine RGB output → Emission Color (with commented alternative for Diffuse BSDF Color)
    state.connect_sockets(principled_tree, combine_rgb, 'Image', emission_shader, 'Color', "combine RGB to emission")
    # Alternative: state.connect_sockets(principled_tree, combine_rgb, 'Image', diffuse_shader, 'Color', "combine RGB to diffuse")
    
    # Connect emission to material output using helper function
    if not _connect_emission_to_material_output(emission_shader, principled_tree, root_tree, state, "emission"):
        return None
    
    return emission_shader


def _connect_emission_to_material_output(emission_shader, principled_tree, root_tree, state, debug_name="emission"):
    """
    Connect an emission shader to the material output, handling both root and nested group cases.
    
    Args:
        emission_shader: The emission shader node to connect
        principled_tree: The node tree containing the Principled BSDF
        root_tree: The root material node tree
        state: NodeGraphState for safe node manipulation
        debug_name: Debug name for logging
    
    Returns:
        True if connection was successful, False otherwise
    """
    def debug_print(*msgs):
        print("      ", *msgs)
        return
    
    # Find or create Material Output node
    material_output = None
    for node in root_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL':
            material_output = node
            break
    
    if not material_output:
        material_output = state.add_node(root_tree, 'ShaderNodeOutputMaterial')
    
    # Connect Emission → Material Output Surface
    if principled_tree == root_tree:
        # Principled is in root tree, connect directly
        state.connect_sockets(root_tree, emission_shader, 'Emission', material_output, 'Surface', f"{debug_name} to material output")
        return True
    else:
        # Principled is in nested group, need to route through group node
        # Find the group node that contains this tree
        group_node = None
        def find_group_node(tree, target_tree):
            for node in tree.nodes:
                if node.type == 'GROUP' and node.node_tree == target_tree:
                    return node
                if node.type == 'GROUP' and node.node_tree:
                    result = find_group_node(node.node_tree, target_tree)
                    if result:
                        return result
            return None
        
        group_node = find_group_node(root_tree, principled_tree)
        if group_node:
            # Create temp group output and connect emission to it
            temp_output = state.add_node(principled_tree, 'ShaderNodeOutputMaterial')
            state.connect_sockets(principled_tree, emission_shader, 'Emission', temp_output, 'Surface', f"{debug_name} to temp output")
            
            # Connect group output to root material output
            if group_node.outputs and len(group_node.outputs) > 0:
                state.connect_sockets(root_tree, group_node, group_node.outputs[0].name, material_output, 'Surface', "group output to material output")
            return True
        else:
            debug_print(f"ERROR: Could not find group node for nested Principled BSDF in {debug_name} baking")
            return False


def bake_packed_texture(
    material: bpy.types.Material,
    obj: bpy.types.Object,
    dtp_format: str,
    resolution: Optional[Tuple[int, int]] = None,
    max_resolution: Optional[Tuple[int, int]] = None
) -> Optional[bpy.types.Image]:
    """
    Bake a packed texture using DTP format string.
    
    Args:
        material: The material containing the socket to bake
        obj: An object with this material assigned (used for baking)
        dtp_format: Format string like "me-sp-ro", "rgba", "ng-ng-ng-nx"
        resolution: Optional tuple of (width, height) for exact output texture size. If set, skips optimization.
        max_resolution: Optional tuple of (width, height) for maximum texture size. Used with optimization.
    
    Returns:
        Baked image or None if baking failed
    """
    def debug_print(*msgs):
        print("      ", *msgs)
        return
    
    if not material.use_nodes:
        return None
    
    root_tree = material.node_tree
    principled = find_principled_bsdf(material)
    
    if not principled:
        return None
    
    # Ensure the object has UV coordinates
    if not _ensure_uv_map(obj):
        debug_print(f"Warning: Could not ensure UV map for object {obj.name}")
        return None
    
    # Find which node tree contains the Principled BSDF
    principled_tree = _find_node_tree_containing_node(material, principled)
    if not principled_tree:
        debug_print(f"ERROR: Could not find node tree containing Principled BSDF")
        return None
    
    # Parse format string to channels
    try:
        channels = _parse_format_string(dtp_format)
    except ValueError as e:
        debug_print(f"ERROR: {e}")
        return None
    
    # Determine resolution based on user input and material analysis
    width, height = _determine_bake_resolution(
        resolution, max_resolution, dtp_format, channels, principled, material, debug_print
    )
    
    # Create state tracker for safe node manipulation (used for all bake operations)
    state = NodeGraphState(material, root_tree, principled_tree)
    
    # Store original render settings
    scene = bpy.context.scene
    original_engine = scene.render.engine
    original_samples = scene.cycles.samples if hasattr(scene, 'cycles') else None
    original_film_transparent = scene.render.film_transparent
    
    # Setup render settings for baking (needed for all bake operations)
    scene.render.engine = 'CYCLES'
    scene.render.film_transparent = False
    
    if hasattr(scene, 'cycles'):
        scene.cycles.samples = 1
    
    # Setup object selection and context (needed for all bake operations)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    
    # Ensure we're in OBJECT mode
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    
    try:
        # Determine bake type based on parsed channels
        bake_type = _get_bake_type_for_channels(channels)
        
        # Handle special cases for normal maps
        if bake_type == 'NORMAL':
            # Use existing NORMAL bake logic
            debug_print(f"Baking normal map: {dtp_format}")
            
            normal_socket = principled.inputs.get('Normal')
            if not normal_socket:
                debug_print("Normal socket not found")
                return None
            
            # Connect Normal socket to Material Output
            material_output = None
            for node in root_tree.nodes:
                if node.type == 'OUTPUT_MATERIAL':
                    material_output = node
                    break
            
            if not material_output:
                material_output = state.add_node(root_tree, 'ShaderNodeOutputMaterial')
            
            if principled_tree == root_tree:
                # Principled is in root, connect directly
                if normal_socket.is_linked:
                    from_socket = normal_socket.links[0].from_socket
                    state.connect_sockets(root_tree, from_socket.node, from_socket.name, material_output, 'Surface', "normal to material output")
            else:
                # Handle nested group case - route through group node
                group_node = None
                def find_group_node(tree, target_tree):
                    for node in tree.nodes:
                        if node.type == 'GROUP' and node.node_tree == target_tree:
                            return node
                        if node.type == 'GROUP' and node.node_tree:
                            result = find_group_node(node.node_tree, target_tree)
                            if result:
                                return result
                    return None
                
                group_node = find_group_node(root_tree, principled_tree)
                if group_node:
                    # Create temp group output and connect normal to it
                    temp_output = state.add_node(principled_tree, 'ShaderNodeOutputMaterial')
                    if normal_socket.is_linked:
                        from_socket = normal_socket.links[0].from_socket
                        state.connect_sockets(principled_tree, from_socket.node, from_socket.name, temp_output, 'Surface', "normal to temp output")
                    
                    # Connect group output to root material output
                    if group_node.outputs and len(group_node.outputs) > 0:
                        state.connect_sockets(root_tree, group_node, group_node.outputs[0].name, material_output, 'Surface', "group output to material output")
                else:
                    debug_print("ERROR: Could not find group node for nested Principled BSDF in normal baking")
                    return None
            
            # Perform the bake using helper function
            return _render_bake_to_image(
                material, obj, root_tree, state, dtp_format, width, height,
                bake_type='NORMAL',
                has_alpha=False,
                resolution=resolution,
                max_resolution=max_resolution,
                normal_space='TANGENT',
                debug_print=debug_print
            )
        
        # Handle EMIT path
        if len(channels) <= 3:
            # RGB-only baking (1 bake, no packing)
            debug_print(f"Baking RGB channels: {channels}")
            
            # Build shader graph
            result = _build_emit_shader_graph(material, channels, state, principled_tree, root_tree)
            if not result:
                debug_print("Failed to build shader graph")
                return None
            
            # Perform the bake using helper function
            return _render_bake_to_image(
                material, obj, root_tree, state, dtp_format, width, height,
                bake_type='EMIT',
                has_alpha=False,
                resolution=resolution,
                max_resolution=max_resolution,
                debug_print=debug_print
            )
        
        else:
            # RGBA baking (2 bakes + numpy packing)
            debug_print(f"Baking RGBA channels: {channels}")
            
            # State tracker already created at function start
            
            # Build shader graph for RGB (first 3 channels)
            rgb_channels = channels[:3]
            rgb_emission = _build_emit_shader_graph(material, rgb_channels, state, principled_tree, root_tree)
            if not rgb_emission:
                debug_print("Failed to build RGB shader graph")
                return None
            
            # Bake RGB using helper function
            rgb_image = _render_bake_to_image(
                material, obj, root_tree, state, f"{dtp_format}_rgb", width, height,
                bake_type='EMIT',
                has_alpha=False,
                resolution=resolution,
                max_resolution=None,  # Don't optimize intermediate image
                debug_print=debug_print,
                skip_optimization=True  # Skip optimization for intermediate image
            )
            if not rgb_image:
                return None
            
            alpha_channel = channels[3]
            debug_print(f"Baking alpha channel: {alpha_channel}")
            
            
            alpha_source = _resolve_socket_source(material, alpha_channel, state, principled_tree)
            if not alpha_source:
                debug_print(f"Could not resolve alpha channel: {alpha_channel}")
                return None
            
            alpha_emission = state.add_node(principled_tree, 'ShaderNodeEmission')
            
            if hasattr(alpha_source, 'node') and hasattr(alpha_source, 'name'):
                state.connect_sockets(principled_tree, alpha_source.node, alpha_source.name, alpha_emission, 'Color', f"alpha {alpha_channel} to emission")
            else:
                # It's an unconnected socket - create a Value node with the default value
                value_node = state.add_node(principled_tree, 'ShaderNodeValue')
                value_node.outputs[0].default_value = alpha_source.default_value
                state.connect_sockets(principled_tree, value_node, 'Value', alpha_emission, 'Color', f"default alpha {alpha_channel} to emission")
            
            # Connect alpha emission to material output using helper function
            if not _connect_emission_to_material_output(alpha_emission, principled_tree, root_tree, state, "alpha emission"):
                return None
            
            # Bake Alpha using helper function
            alpha_image = _render_bake_to_image(
                material, obj, root_tree, state, f"{dtp_format}_alpha", width, height,
                bake_type='EMIT',
                has_alpha=False,
                resolution=resolution,
                max_resolution=None,  # Don't optimize intermediate image
                debug_print=debug_print,
                skip_optimization=True  # Skip optimization for intermediate image
            )
            if not alpha_image:
                return None
            
            debug_print("Packing RGB + A with numpy")
            from .texture_utils import _image_to_np, _np_to_image_pixels
            
            rgb_array = _image_to_np(rgb_image)
            alpha_array = _image_to_np(alpha_image)
            
            rgba_array = rgb_array.copy()
            rgba_array[:, :, 3] = alpha_array[:, :, 0]  # Use R channel as alpha
            
            final_image = bpy.data.images.new(
                name=f"bake_{material.name}_{dtp_format}",
                width=width,
                height=height,
                alpha=True,
                float_buffer=False
            )
            
            _np_to_image_pixels(final_image, rgba_array)
            
            bpy.data.images.remove(rgb_image)
            bpy.data.images.remove(alpha_image)
            
            # Restore state after alpha bake
            state.restore()
            
            # Post-baking optimization: analyze for minimum safe resolution (only if resolution not specified)
            if resolution is None:
                final_image = _optimize_baked_image(final_image, obj, max_resolution)
            
            debug_print(f"🍞 RGBA bake finished")
            return final_image
        
    except Exception as e:
        debug_print(f"ERROR: Failed to bake packed texture {dtp_format}: {e}")
        traceback.print_exc()
        return None
        
    finally:
        # Restore render settings
        scene.render.engine = original_engine
        scene.render.film_transparent = original_film_transparent
        if original_samples is not None and hasattr(scene, 'cycles'):
            scene.cycles.samples = original_samples
        

def _render_bake_to_image(
    material: bpy.types.Material,
    obj: bpy.types.Object,
    root_tree: bpy.types.NodeTree,
    state: NodeGraphState,
    dtp_format: str,
    width: int,
    height: int,
    bake_type: str,
    has_alpha: bool = False,
    resolution: Optional[Tuple[int, int]] = None,
    max_resolution: Optional[Tuple[int, int]] = None,
    normal_space: Optional[str] = None,
    debug_print = None,
    skip_optimization: bool = False
) -> Optional[bpy.types.Image]:
    """
    Perform the render with configs.
    
    Args:
        material: Material to bake from
        obj: Object to bake to
        root_tree: Root node tree
        state: Node graph state tracker
        dtp_format: DTP format string for image naming
        width, height: Image dimensions
        bake_type: 'NORMAL' or 'EMIT'
        has_alpha: Whether image should have alpha channel
        resolution: Optional fixed resolution (skips optimization)
        max_resolution: Optional maximum resolution for optimization
        normal_space: Optional normal space for NORMAL bakes (e.g., 'TANGENT')
        debug_print: Debug print function
        skip_optimization: If True, skip post-bake optimization (useful for intermediate images)
        
    Returns:
        Baked image or None if failed
    """
    # Create target image
    target_image = bpy.data.images.new(
        name=f"bake_{material.name}_{dtp_format}",
        width=width,
        height=height,
        alpha=has_alpha,
        float_buffer=False
    )
    
    # Create image texture node in ROOT tree
    img_node = state.add_node(root_tree, 'ShaderNodeTexImage')
    img_node.image = target_image
    img_node.select = True
    root_tree.nodes.active = img_node
    
    # Perform the bake
    bake_start_time = time.time()
    bake_kwargs = {
        'type': bake_type,
        'margin': 256,
        'use_selected_to_active': False
    }
    if normal_space:
        bake_kwargs['normal_space'] = normal_space
    
    bpy.ops.object.bake(**bake_kwargs)
    bake_end_time = time.time()
    bake_duration = int(bake_end_time - bake_start_time)
    debug_print(f"🍞 {bake_type} bake finished in {bake_duration} seconds")
    
    # Restore state after bake
    state.restore()
    
    # Post-baking optimization: analyze for minimum safe resolution (only if resolution not specified and optimization not skipped)
    if resolution is None and not skip_optimization:
        target_image = _optimize_baked_image(target_image, obj, max_resolution)
    
    return target_image


def _optimize_baked_image(image: bpy.types.Image, obj: bpy.types.Object, max_resolution: Optional[Tuple[int, int]] = None) -> bpy.types.Image:
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
        print("      ", *msgs)
        return
    
    if not obj or obj.type != 'MESH':
        return image
    
    try:
        start_time = time.time()
        mip_results = analyze_mip_stats(obj, image)
        
        if mip_results and mip_results['min_safe_resolution']:
            optimal_size = mip_results['min_safe_resolution']
            current_size = (image.size[0], image.size[1])
            
            # Apply max_resolution cap if provided
            if max_resolution:
                max_width, max_height = max_resolution
                optimal_size = (min(optimal_size[0], max_width), min(optimal_size[1], max_height))
            
            if optimal_size != current_size:
                debug_print(f"🔍 Optimizing from {current_size[0]}x{current_size[1]} to {optimal_size[0]}x{optimal_size[1]}")
                optimized_output = resize_image_to_size(image, optimal_size[0], optimal_size[1])
                optimized_output.name = f"optimized_{image.name}"
                bpy.data.images.remove(image)
                image = optimized_output
                debug_print(f"✅ Optimization complete")
            else:
                debug_print(f"🔍 No optimization needed (already optimal)")
        
        analysis_time = int(time.time() - start_time)
        debug_print(f"🔍 Optimization analysis finished in {analysis_time} s")
        
    except Exception as e:
        debug_print(f"⚠️ Packed texture optimization failed: {e}")
    
    return image


def _determine_bake_resolution(
    resolution: Optional[Tuple[int, int]], 
    max_resolution: Optional[Tuple[int, int]], 
    dtp_format: str, 
    channels: list, 
    principled: bpy.types.ShaderNode, 
    material: bpy.types.Material, 
    debug_print
) -> Tuple[int, int]:
    """
    Determine the optimal resolution for baking based on user input and material analysis.
    
    Args:
        resolution: User-specified exact resolution (takes priority)
        max_resolution: User-specified maximum resolution cap
        dtp_format: DTP format string for determining relevant sockets
        channels: Parsed channel list from format string
        principled: Principled BSDF node
        material: Material containing the node tree
        debug_print: Debug print function
        
    Returns:
        Tuple of (width, height) for baking
    """
    # If user specified exact resolution, use it
    if resolution is not None:
        debug_print(f"🔧 Baking {dtp_format} at {resolution[0]}x{resolution[1]}")
        return resolution
    
    # Determine relevant sockets based on the DTP format channels
    relevant_sockets = set()
    for channel in channels:
        if channel in DTP_SOCKET_MAP:
            socket_mapping = DTP_SOCKET_MAP[channel]
            if isinstance(socket_mapping, tuple):
                # RGB channel mapping like ('Base Color', 0)
                relevant_sockets.add(socket_mapping[0])
            else:
                # Direct socket mapping like 'Metallic'
                relevant_sockets.add(socket_mapping)
    
    # Auto-detect resolution from material's node tree
    detected_resolution = None
    for socket_name in relevant_sockets:
        socket = principled.inputs.get(socket_name)
        if socket and socket.is_linked:
            res = find_largest_texture_resolution(socket, material)
            if res:
                if detected_resolution is None or (res[0] * res[1] > detected_resolution[0] * detected_resolution[1]):
                    detected_resolution = res
    
    # Use detected resolution or fall back to default
    if detected_resolution:
        width, height = detected_resolution
        debug_print(f"🔧 Baking {dtp_format} at {width}x{height} (detected from material)")
    else:
        width, height = 512, 512
        debug_print(f"🔧 Baking {dtp_format} at 512x512 (default)")
    
    # Apply max_resolution cap if provided
    if max_resolution:
        max_width, max_height = max_resolution
        if width > max_width or height > max_height:
            width = min(width, max_width)
            height = min(height, max_height)
            debug_print(f"🔧 Capped at {width}x{height} (max_resolution limit)")
    
    return (width, height)


def create_default_texture(width: int, height: int, color: Tuple[float, float, float, float]) -> bpy.types.Image:
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
        name=f"default_{width}x{height}",
        width=width,
        height=height,
        alpha=True
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
        print("      ", *msgs)
        return

    if obj.type != 'MESH':
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
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Select all
        bpy.ops.mesh.select_all(action='SELECT')
        
        # Create UV unwrap
        bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.1)
        
        # Return to original mode
        bpy.ops.object.mode_set(mode=current_mode)
        
        return True
    except Exception as e:
        debug_print(f"ERROR: Failed to create UV map for {obj.name}: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
        return False


def _find_node_tree_containing_node(material: bpy.types.Material, target_node) -> Optional[bpy.types.NodeTree]:
    """Find which node tree (root or group) contains a specific node."""
    # Check root tree
    if target_node in material.node_tree.nodes.values():
        return material.node_tree
    
    # Check nested groups recursively
    def search_groups(node_tree):
        for node in node_tree.nodes:
            if node.type == 'GROUP' and node.node_tree:
                if target_node in node.node_tree.nodes.values():
                    return node.node_tree
                result = search_groups(node.node_tree)
                if result:
                    return result
        return None
    
    return search_groups(material.node_tree)


# bake_socket() and bake_and_save_socket() functions removed - replaced by bake_packed_texture()
