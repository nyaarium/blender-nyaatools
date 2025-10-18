"""Texture baking utilities for rendering Blender material sockets to texture maps."""

import bpy
import numpy as np
import os
import time
import traceback
from typing import Optional, Tuple

from .material_analyzer import find_principled_bsdf


def safe_link(node_tree: bpy.types.NodeTree, from_socket, to_socket, *debug_parts):
    """
    Safely create a link between sockets, removing any existing connections to the target socket first.

    Args:
        node_tree: The node tree containing the sockets
        from_socket: Source socket to connect from
        to_socket: Target socket to connect to
        *debug_parts: Optional debug message parts:
            - 0 parts: No debug logging
            - 1 part: Simple message
            - 2+ parts: "part1 -> part2 -> part3..." format
    """
    def debug_print(*msgs):
        print("          ", *msgs)
        return

    # Handle debug logging based on number of parts provided
    if len(debug_parts) == 1:
        debug_print(f"🧦 {debug_parts[0]}")
    elif len(debug_parts) >= 2:
        arrow_parts = [str(part) for part in debug_parts]
        debug_print(f"🧦 {' -> '.join(arrow_parts)}")

    # Disconnect any existing connections to the target socket
    if to_socket.is_linked:
        existing_links = list(to_socket.links)
        for link in existing_links:
            node_tree.links.remove(link)

    # Create the new connection
    node_tree.links.new(from_socket, to_socket)


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


def bake_socket(
    material: bpy.types.Material,
    obj: bpy.types.Object,
    socket_name: str,
    resolution: Tuple[int, int],
    is_normal: bool = False,
    default_value: Optional[Tuple] = None
) -> Optional[bpy.types.Image]:
    """
    Bake a specific socket from a material's Principled BSDF to a texture.
    
    Places temporary bake nodes in the same node tree as the Principled BSDF
    to avoid circular dependencies.
    
    Args:
        material: The material containing the socket to bake
        obj: An object with this material assigned (used for baking)
        socket_name: Name of the Principled BSDF input socket to bake
        resolution: Tuple of (width, height) for the output texture
        is_normal: True if baking a normal map socket
        default_value: Default value to use if socket is not connected (e.g., (0.5, 0.5, 1.0) for normals)
    
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
    
    # Check if the socket exists
    socket = principled.inputs.get(socket_name)
    if not socket:
        return None
    
    # Ensure the object has UV coordinates
    if not _ensure_uv_map(obj):
        debug_print(f"Warning: Could not ensure UV map for object {obj.name}")
        return None
    
    width, height = resolution
    
    # Find which node tree contains the Principled BSDF
    principled_tree = _find_node_tree_containing_node(material, principled)
    if not principled_tree:
        debug_print(f"ERROR: Could not find node tree containing Principled BSDF")
        return None
    
    # Store original node setup to restore later
    original_links = []
    root_output_node = None
    temp_output_node = None
    bake_bsdf = None
    img_node = None
    
    # Find root material output node
    for node in root_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL':
            root_output_node = node
            break
    
    if not root_output_node:
        root_output_node = root_tree.nodes.new('ShaderNodeOutputMaterial')
    
    # Store original root output connections
    if root_output_node.inputs['Surface'].is_linked:
        for link in root_output_node.inputs['Surface'].links:
            original_links.append({
                'from_socket': link.from_socket,
                'to_socket': root_output_node.inputs['Surface']
            })
    
    # Store original render settings
    scene = bpy.context.scene
    original_engine = scene.render.engine
    original_samples = scene.cycles.samples if hasattr(scene, 'cycles') else None
    original_film_transparent = scene.render.film_transparent
    
    try:
        # Determine if we need alpha channel (only for Base Color socket)
        # Alpha socket is baked as monochrome RGB, then packed into diffuse alpha channel
        needs_alpha = socket_name == 'Base Color'
        
        # Create target image for baking
        target_image = bpy.data.images.new(
            name=f"bake_{material.name}_{socket_name.replace(' ', '_')}",
            width=width,
            height=height,
            alpha=needs_alpha,
            float_buffer=False
        )
        
        # Create image texture node in ROOT tree (this is where Blender expects it)
        img_node = root_tree.nodes.new('ShaderNodeTexImage')
        img_node.image = target_image
        img_node.select = True
        root_tree.nodes.active = img_node
        
        # Create temporary bake BSDF in the SAME tree as the Principled BSDF
        if not is_normal:
            # Use Diffuse BSDF for baking
            bake_bsdf = principled_tree.nodes.new('ShaderNodeBsdfDiffuse')
            
            # Connect the socket to the bake BSDF
            if socket.is_linked:
                from_socket = socket.links[0].from_socket
                safe_link(principled_tree, from_socket, bake_bsdf.inputs['Color'], socket_name, "bake BSDF Color")
            else:
                # Use the socket's default value or provided default
                val = default_value if default_value is not None else (socket.default_value if hasattr(socket, 'default_value') else None)
                if val is not None:
                    debug_print(f"Using value: {val}")
                    if isinstance(val, (float, int)):
                        bake_bsdf.inputs['Color'].default_value = (val, val, val, 1.0)
                    elif hasattr(val, '__len__'):
                        if len(val) == 4:
                            bake_bsdf.inputs['Color'].default_value = val
                        elif len(val) == 3:
                            bake_bsdf.inputs['Color'].default_value = (*val, 1.0)
        else:
            # For normal maps with no connection, use emission shader with default normal value
            if not socket.is_linked:
                val = default_value if default_value is not None else (0.5, 0.5, 1.0)
                debug_print(f"Normal map not connected, using default: {val}")
                
                # Create emission shader for the default value
                bake_bsdf = principled_tree.nodes.new('ShaderNodeEmission')
                emission_color = (*val, 1.0) if len(val) == 3 else val

                # Assign desired flat normal color
                bake_bsdf.inputs['Color'].default_value = emission_color
        
        # Connect the bake BSDF to material output
        if principled_tree != root_tree:
            # Principled is in a nested group - need to route through group node
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
                # Create temp group output and connect bake BSDF to it
                temp_output_node = principled_tree.nodes.new('ShaderNodeOutputMaterial')
                if not is_normal or (is_normal and not socket.is_linked):
                    # Connect emission/diffuse BSDF for non-normal or unconnected normal
                    output_socket = bake_bsdf.outputs.get('BSDF') or bake_bsdf.outputs.get('Emission')
                    safe_link(principled_tree, output_socket, temp_output_node.inputs['Surface'], "bake shader", "temp output Surface")
                # Connect group output to root material output
                if group_node.outputs and len(group_node.outputs) > 0:
                    safe_link(root_tree, group_node.outputs[0], root_output_node.inputs['Surface'], "group output", "root material output")
            else:
                debug_print(f"ERROR: Could not find group node for nested Principled BSDF")
                return None
        else:
            # Principled is in root, connect directly to root output
            if not is_normal or (is_normal and not socket.is_linked):
                # Connect emission/diffuse BSDF for non-normal or unconnected normal
                output_socket = bake_bsdf.outputs.get('BSDF') or bake_bsdf.outputs.get('Emission')
                safe_link(root_tree, output_socket, root_output_node.inputs['Surface'], "bake shader", "root material output")
        
        # Setup render settings for baking
        scene.render.engine = 'CYCLES'
        scene.render.film_transparent = False
        
        if hasattr(scene, 'cycles'):
            scene.cycles.samples = 1
        
        # Select the object and set it active
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        
        # Ensure we're in OBJECT mode
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # Perform the bake
        bake_start_time = time.time()
        if is_normal:
            if socket.is_linked:
                # Connected normal maps: bake NORMAL
                bpy.ops.object.bake(
                    type='NORMAL',
                    margin=128,
                    use_selected_to_active=False,
                    normal_space='TANGENT'
                )
            else:
                # Unlinked normal maps: bake EMIT from the emission shader color
                debug_print("Normal (unlinked): baking EMIT flat normal")
                bpy.ops.object.bake(
                    type='EMIT',
                    margin=128,
                    use_selected_to_active=False
                )
        else:
            # Other sockets: bake DIFFUSE color only
            bpy.ops.object.bake(
                type='DIFFUSE',
                pass_filter={'COLOR'},
                margin=128,
                use_selected_to_active=False
            )
        
        bake_end_time = time.time()
        bake_duration = int(bake_end_time - bake_start_time)
        debug_print(f"🍞 Bake finished in {bake_duration} seconds")
        
        return target_image
        
    except Exception as e:
        debug_print(f"ERROR: Failed to bake socket {socket_name}: {e}")
        traceback.print_exc()
        return None
        
    finally:
        # Restore render settings
        scene.render.engine = original_engine
        scene.render.film_transparent = original_film_transparent
        if original_samples is not None and hasattr(scene, 'cycles'):
            scene.cycles.samples = original_samples
        
        # Remove temporary nodes from appropriate trees
        if img_node and img_node.name in root_tree.nodes:
            root_tree.nodes.remove(img_node)
        if bake_bsdf and bake_bsdf.name in principled_tree.nodes:
            principled_tree.nodes.remove(bake_bsdf)
        if temp_output_node and temp_output_node.name in principled_tree.nodes:
            principled_tree.nodes.remove(temp_output_node)
        
        # Restore original connections
        for link in list(root_output_node.inputs['Surface'].links):
            root_tree.links.remove(link)

        for link_data in original_links:
            safe_link(root_tree, link_data['from_socket'], link_data['to_socket'], "restoring original connection")


def bake_and_save_socket(
    material: bpy.types.Material,
    obj: bpy.types.Object,
    socket_name: str,
    resolution: Tuple[int, int],
    output_path: str,
    is_normal: bool = False,
    default_value: Optional[Tuple] = None
) -> bool:
    """
    Bake a socket and save directly to a PNG file.
    
    Args:
        material: The material containing the socket
        obj: Object with the material (used for baking)
        socket_name: Name of the Principled BSDF socket to bake
        resolution: Output resolution (width, height)
        output_path: Path to save the PNG image
        is_normal: True if baking a normal map
        default_value: Default value to use if socket is not connected
    
    Returns:
        True if successful, False otherwise
    """
    def debug_print(*msgs):
        print("      ", *msgs)
        return

    img = bake_socket(material, obj, socket_name, resolution, is_normal, default_value)
    
    if not img:
        return False
    
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save the image
        img.filepath_raw = output_path
        img.file_format = 'PNG'
        img.save()
        
        # Clean up the image from Blender's memory
        bpy.data.images.remove(img)
        
        return True
    except Exception as e:
        debug_print(f"ERROR: Failed to save baked image to {output_path}: {e}")
        if img and img.name in bpy.data.images:
            bpy.data.images.remove(img)
        return False
