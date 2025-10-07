"""Texture baking utilities for rendering Blender material sockets to texture maps."""

import bpy
import os
from typing import Optional, Tuple


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
    is_normal: bool = False
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
    
    Returns:
        Baked image or None if baking failed
    """
    def debug_print(*msgs):
        print("      ", *msgs)
        return

    from .material_analyzer import find_principled_bsdf
    
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
                # Use the socket's default value
                if hasattr(socket, 'default_value'):
                    val = socket.default_value
                    debug_print(f"Using value: {val}")
                    if isinstance(val, (float, int)):
                        bake_bsdf.inputs['Color'].default_value = (val, val, val, 1.0)
                    elif hasattr(val, '__len__'):
                        if len(val) == 4:
                            bake_bsdf.inputs['Color'].default_value = val
                        elif len(val) == 3:
                            bake_bsdf.inputs['Color'].default_value = (*val, 1.0)
        
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
                if not is_normal:
                    safe_link(principled_tree, bake_bsdf.outputs['BSDF'], temp_output_node.inputs['Surface'], "bake BSDF", "temp output Surface")
                # Connect group output to root material output
                if group_node.outputs and len(group_node.outputs) > 0:
                    safe_link(root_tree, group_node.outputs[0], root_output_node.inputs['Surface'], "group output", "root material output")
            else:
                debug_print(f"ERROR: Could not find group node for nested Principled BSDF")
                return None
        else:
            # Principled is in root, connect directly to root output
            if not is_normal:
                safe_link(root_tree, bake_bsdf.outputs['BSDF'], root_output_node.inputs['Surface'], "bake BSDF", "root material output")
        
        # Setup render settings for baking
        scene.render.engine = 'CYCLES'
        scene.render.film_transparent = False
        
        if hasattr(scene, 'cycles'):
            scene.cycles.samples = 1
        
        # Select the object and set it active
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        
        debug_print(f"Baking {'NORMAL' if is_normal else 'DIFFUSE'} at {width}x{height}...")

        # Ensure we're in OBJECT mode
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # Perform the bake
        if is_normal:
            bpy.ops.object.bake(
                type='NORMAL',
                margin=32,
                use_selected_to_active=False,
                normal_space='TANGENT'
            )
        else:
            # Bake DIFFUSE instead of EMIT
            bpy.ops.object.bake(
                type='DIFFUSE',
                pass_filter={'COLOR'},
                margin=32,
                use_selected_to_active=False
            )
        
        debug_print(f"Bake completed! Checking for optimization...")
        
        # Apply solid color optimization if applicable
        optimized_image = scan_and_resize_solids(target_image, obj)
        if optimized_image != target_image:
            debug_print(f"🎨 Optimized to solid color texture")
            # Clean up original if we created a new optimized version
            if optimized_image.name != target_image.name:
                bpy.data.images.remove(target_image)
            return optimized_image
        
        return target_image
        
    except Exception as e:
        debug_print(f"ERROR: Failed to bake socket {socket_name}: {e}")
        import traceback
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
    is_normal: bool = False
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
    
    Returns:
        True if successful, False otherwise
    """
    def debug_print(*msgs):
        print("      ", *msgs)
        return

    img = bake_socket(material, obj, socket_name, resolution, is_normal)
    
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


def iterate_36_15_uv_point(face_vertices, i):
    """
    Generate UV coordinates for 15 sampling points in a triangular pattern.
    
    Args:
        face_vertices: List of 3 UV coordinates defining the triangle
        i: Index from 0 to 14 for the sampling point
    
    Returns:
        UV coordinate tuple (u, v) for the i-th sampling point
    """
    
    if len(face_vertices) != 3:
        raise ValueError("face_vertices must contain exactly 3 UV coordinates")
    
    if i < 0 or i > 14:
        raise ValueError("i must be between 0 and 14")
    
    # 15 inner points from a 36-point triangular grid
    # These points are mathematically derived to stay within UV tri bounds
    #        .
    #       . .
    #      . x .
    #     . x x .
    #    . x x x .
    #   . x x x x .
    #  . x x x x x .
    # . . . . . . . .
    barycentric_points = [
        (0.143, 0.143, 0.714),
        (0.286, 0.143, 0.571),
        (0.143, 0.286, 0.571),
        (0.429, 0.143, 0.429),
        (0.286, 0.286, 0.429),
        (0.143, 0.429, 0.429),
        (0.571, 0.143, 0.286),
        (0.429, 0.286, 0.286),
        (0.286, 0.429, 0.286),
        (0.143, 0.571, 0.286),
        (0.714, 0.143, 0.143),
        (0.571, 0.286, 0.143),
        (0.429, 0.429, 0.143),
        (0.286, 0.571, 0.143),
        (0.143, 0.714, 0.143)
    ]
    
    u_bary, v_bary, w_bary = barycentric_points[i]
    
    # Interpolate using barycentric coordinates
    v0, v1, v2 = face_vertices
    
    u = u_bary * v0[0] + v_bary * v1[0] + w_bary * v2[0]
    v = u_bary * v0[1] + v_bary * v1[1] + w_bary * v2[1]
    
    return (u, v)


def scan_uv_tile(face_vertices, target_image, threshold=0.01):
    """
    Analyze a single UV face for color consistency.
    
    Args:
        face_vertices: List of 3 UV coordinates defining the triangle
        target_image: The texture to sample from
        threshold: Color variance threshold (default 0.01)
    
    Returns:
        Tuple (is_solid, avg_color) where is_solid is bool and avg_color is (R,G,B,A)
    """
    def debug_print(*msgs):
        print("        ", *msgs)
        return
    
    if not target_image or not target_image.pixels:
        return False, (0.0, 0.0, 0.0, 1.0)
    
    width, height = target_image.size
    pixels = target_image.pixels
    channels = 4 if target_image.channels == 4 else 3
    
    min_r = min_g = min_b = float('inf')
    max_r = max_g = max_b = float('-inf')
    total_r = total_g = total_b = 0.0
    valid_samples = 0
    
    # Sample 15 points across the triangle
    for i in range(15):
        try:
            u, v = iterate_36_15_uv_point(face_vertices, i)
            
            # Convert UV to pixel coordinates
            x = int(u * width) % width
            y = int(v * height) % height
            
            # Get pixel index
            pixel_idx = (y * width + x) * channels
            
            # Sample RGB values
            r = pixels[pixel_idx]
            g = pixels[pixel_idx + 1] 
            b = pixels[pixel_idx + 2]
            
            # Update min/max/total
            min_r = min(min_r, r)
            min_g = min(min_g, g)
            min_b = min(min_b, b)
            max_r = max(max_r, r)
            max_g = max(max_g, g)
            max_b = max(max_b, b)
            
            total_r += r
            total_g += g
            total_b += b
            valid_samples += 1
            
        except Exception as e:
            continue
    
    if valid_samples == 0:
        debug_print("No valid samples collected")
        return False, (0.0, 0.0, 0.0, 1.0)
    
    # Calculate variance
    variance_r = max_r - min_r
    variance_g = max_g - min_g
    variance_b = max_b - min_b
    max_variance = max(variance_r, variance_g, variance_b)
    
    # Check if variance exceeds threshold
    is_solid = max_variance <= threshold
    
    if is_solid:
        # Calculate average color
        avg_r = total_r / valid_samples
        avg_g = total_g / valid_samples
        avg_b = total_b / valid_samples
        avg_color = (avg_r, avg_g, avg_b, 1.0)
    else:
        avg_color = (0.0, 0.0, 0.0, 1.0)
    
    return is_solid, avg_color


def scan_and_resize_solids(target_image, obj):
    """
    Scan UV faces and optimize solid color textures to 8x8 pixels.
    Only works on triangulated meshes.
    
    Args:
        target_image: The baked texture to analyze
        obj: The object with UV mapping
    
    Returns:
        Either target_image (if variance detected) or new 8x8 solid color image
    """
    def debug_print(*msgs):
        print("      ", *msgs)
        return
    
    if not target_image or not obj or obj.type != 'MESH':
        debug_print("Invalid input for solid color optimization")
        return target_image
    
    mesh = obj.data
    if not mesh.uv_layers:
        debug_print("No UV layers found")
        return target_image
    
    uv_layer = mesh.uv_layers[0]
    
    solid_colors = []
    
    # Scan each UV face
    for face_idx, face in enumerate(mesh.polygons):
        if len(face.vertices) != 3:
            continue
        
        # Get UV coordinates for this face
        face_vertices = []
        for vert_idx in face.vertices:
            loop_idx = face.loop_start + list(face.vertices).index(vert_idx)
            uv_co = uv_layer.data[loop_idx].uv
            face_vertices.append((uv_co.x, uv_co.y))
        
        
        # Scan this UV tile
        is_solid, avg_color = scan_uv_tile(face_vertices, target_image)
        
        if not is_solid:
            return target_image
        
        solid_colors.append(avg_color)
    
    if not solid_colors:
        return target_image
    
    # Check if all faces have the same color
    first_color = solid_colors[0]
    for i, color in enumerate(solid_colors[1:], 1):
        if abs(color[0] - first_color[0]) > 0.01 or \
           abs(color[1] - first_color[1]) > 0.01 or \
           abs(color[2] - first_color[2]) > 0.01:
            debug_print(f"Different solid colors detected, keeping original texture")
            return target_image
    
    # All faces are the same solid color - create optimized 8x8 texture
    debug_print(f"All faces are solid color: {first_color}")
    optimized_image = create_default_texture(8, 8, first_color)
    optimized_image.name = f"optimized_{target_image.name}"
    
    return optimized_image


def generate_barycentric_sample_points():
    """
    Generate barycentric coordinates for sampling a triangle.
    Creates a 36-point triangular grid and returns the 15 inner points.
    
    The pattern looks like this:
         .
        . .
       . x .
      . x x .
     . x x x .
    . x x x x .
   . x x x x x .
  . . . . . . . .
  
  Where 'x' are the sampled inner points and '.' are edge points.
  
    Returns:
        list: List of 15 (u, v, w) barycentric coordinate tuples
    """
    # Generate all 36 points in the triangular grid
    all_points = []
    for i in range(8):  # 8 rows
        for j in range(i + 1):  # i+1 points in row i
            # Convert to barycentric coordinates
            u = j / 7.0  # Normalize to [0,1]
            v = (i - j) / 7.0  # Normalize to [0,1] 
            w = 1.0 - u - v  # Ensure u + v + w = 1
            all_points.append((u, v, w))
    
    # Select the 15 inner points (skip edge points)
    inner_points = []
    for i in range(1, 7):  # Skip first and last rows (edges)
        for j in range(1, i):  # Skip first and last points in each row (edges)
            u = j / 7.0
            v = (i - j) / 7.0
            w = 1.0 - u - v
            inner_points.append((u, v, w))
    
    return inner_points
