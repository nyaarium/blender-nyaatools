"""Material analysis utilities for extracting texture information from Blender materials."""

import bpy
from typing import Optional, Tuple, Dict, Set


def find_principled_bsdf(material: bpy.types.Material) -> Optional[bpy.types.ShaderNode]:
    """
    Find the Principled BSDF node connected to the material output.
    
    Args:
        material: The Blender material to search
        
    Returns:
        The Principled BSDF node if found, None otherwise
    """
    if not material.use_nodes:
        return None
    
    node_tree = material.node_tree
    if not node_tree:
        return None
    
    return _find_principled_bsdf_in_tree(node_tree)


def _find_principled_bsdf_in_tree(node_tree: bpy.types.NodeTree) -> Optional[bpy.types.ShaderNode]:
    """
    Find the Principled BSDF node connected to the material output.
    
    Args:
        node_tree: The node tree to search
        
    Returns:
        The Principled BSDF node if found, None otherwise
    """
    def debug_print(*msgs):
        print("      ", *msgs)
        return
    
    if not node_tree:
        return None
    
    # Find material output node
    output_node = None
    for node in node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
            output_node = node
            break
    
    # Fallback to any output if no active output found
    if not output_node:
        for node in node_tree.nodes:
            if node.type == 'OUTPUT_MATERIAL':
                output_node = node
                break
    
    if not output_node:
        debug_print("No Material Output node found in tree")
        return None
    
    surface_input = output_node.inputs.get('Surface')
    if not surface_input or not surface_input.is_linked:
        debug_print("Material Output has no connected Surface input")
        return None
    
    visited_nodes = set()
    return _trace_to_principled_bsdf(surface_input.links[0].from_node, visited_nodes)


def _trace_to_principled_bsdf(node: bpy.types.Node, visited_nodes: set) -> Optional[bpy.types.ShaderNode]:
    """
    Trace through the node tree to find a Principled BSDF node.
    
    Args:
        node: Current node to examine
        visited_nodes: Set of already visited nodes to prevent infinite loops
        
    Returns:
        Principled BSDF node if found, None otherwise
    """
    def debug_print(*msgs):
        print("      ", *msgs)
        return
    
    # Prevent infinite loops
    node_id = str(node.name) + str(id(node))
    if node_id in visited_nodes:
        return None
    visited_nodes.add(node_id)
    
    if node.type == 'BSDF_PRINCIPLED':
        return node
    
    if node.type == 'GROUP':
        if not node.node_tree:
            return None
            
        # Find group output node
        group_output = None
        for group_node in node.node_tree.nodes:
            if group_node.type == 'GROUP_OUTPUT' and group_node.is_active_output:
                group_output = group_node
                break
                
        if not group_output:
            for group_node in node.node_tree.nodes:
                if group_node.type == 'GROUP_OUTPUT':
                    group_output = group_node
                    break
        
        if not group_output:
            return None
            
        # Trace from group output inputs
        for input_socket in group_output.inputs:
            if input_socket.is_linked:
                for link in input_socket.links:
                    result = _trace_to_principled_bsdf(link.from_node, visited_nodes)
                    if result:
                        return result
    
    elif node.type in ['MIX_SHADER', 'ADD_SHADER', 'SHADER_TO_RGB']:
        # Check all shader inputs
        for input_socket in node.inputs:
            if input_socket.is_linked:
                for link in input_socket.links:
                    result = _trace_to_principled_bsdf(link.from_node, visited_nodes)
                    if result:
                        return result
    
    else:
        # Check all inputs for other node types
        for input_socket in node.inputs:
            if input_socket.is_linked:
                for link in input_socket.links:
                    result = _trace_to_principled_bsdf(link.from_node, visited_nodes)
                    if result:
                        return result
    
    return None


def has_socket_input(socket: bpy.types.NodeSocket) -> bool:
    """
    Check if a socket has input connected.
    
    Args:
        socket: The input socket to check
        
    Returns:
        True if socket has input connected, False otherwise
    """
    return socket.is_linked if socket else False


def find_largest_texture_resolution(socket: bpy.types.NodeSocket, material: bpy.types.Material = None) -> Optional[Tuple[int, int]]:
    """
    Find the largest texture resolution in the node tree connected to a socket.
    
    Args:
        socket: The input socket to search from
        material: The material (needed to find group instances in parent tree)
        
    Returns:
        Tuple of (width, height) for the largest texture found, or None if no textures found
    """
    def debug_print(*msgs):
        print("      ", *msgs)
        return
    
    if not socket or not socket.is_linked:
        return None
    
    visited_nodes = {}
    visited_groups = {}
    visited_sockets = {}
    debug_nodes = []
    
    max_resolution = None
    
    # Build group instance map for traversing group boundaries
    group_instances: Dict = {}
    if material and material.node_tree:
        _build_group_instance_map(material.node_tree, group_instances)
    
    # Search material root tree for textures
    if material and material.node_tree:
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                width, height = node.image.size[0], node.image.size[1]
                if max_resolution is None:
                    max_resolution = (width, height)
                elif width * height > max_resolution[0] * max_resolution[1]:
                    max_resolution = (width, height)
    
    def search_node(node, node_tree, depth=0, path=None):
        nonlocal max_resolution
        
        if path is None:
            path = []
        
        node_key = f"{node.name}_{id(node)}"
        if node_key in visited_nodes:
            return
        visited_nodes[node_key] = True
        
        current_path = path + [node_key]
        
        debug_nodes.append(f"{'  ' * depth}{node.type} ({node.name})")
        
        if node.type == 'TEX_IMAGE' and node.image:
            width, height = node.image.size[0], node.image.size[1]
            debug_nodes.append(f"{'  ' * (depth+1)}✓ Found texture: {node.image.name} ({width}x{height})")
            if max_resolution is None:
                max_resolution = (width, height)
            else:
                if width * height > max_resolution[0] * max_resolution[1]:
                    max_resolution = (width, height)
        
        elif node.type == 'GROUP_INPUT' and node_tree in group_instances:
            # Handle group input - traverse back through group boundary
            debug_nodes.append(f"{'  ' * (depth+1)}↑ Crossing group boundary...")
            group_nodes = group_instances[node_tree]
            
            # Search material root tree for textures
            if material and material.node_tree:
                debug_nodes.append(f"{'  ' * (depth+1)}↑ Checking material root tree")
                for root_node in material.node_tree.nodes:
                    if root_node.type == 'TEX_IMAGE' and root_node.image:
                        width, height = root_node.image.size[0], root_node.image.size[1]
                        debug_nodes.append(f"{'  ' * (depth+2)}✓ Found root texture: {root_node.image.name} ({width}x{height})")
                        if max_resolution is None:
                            max_resolution = (width, height)
                        elif width * height > max_resolution[0] * max_resolution[1]:
                            max_resolution = (width, height)
            
            # Traverse through group instances
            for group_node, parent_tree in group_nodes:
                group_key = f"{group_node.name}_{id(group_node)}"
                if group_key in visited_groups:
                    continue
                visited_groups[group_key] = True
                
                debug_nodes.append(f"{'  ' * (depth+1)}↑ To parent via group: {group_node.name}")
                
                for i, group_input_socket in enumerate(group_node.inputs):
                    if group_input_socket.is_linked:
                        socket_key = f"{group_input_socket.name}_{id(group_input_socket)}"
                        if socket_key in visited_sockets:
                            continue
                        visited_sockets[socket_key] = True
                        
                        for link in group_input_socket.links:
                            from_node = link.from_node
                            from_key = f"{from_node.name}_{id(from_node)}"
                            if from_key not in current_path:
                                search_node(from_node, parent_tree, depth + 1, current_path)
        
        elif node.type == 'GROUP' and node.node_tree is not None:
            # Recursively search node group internals
            debug_nodes.append(f"{'  ' * (depth+1)}↓ Entering group: {node.node_tree.name}")
            for group_node in node.node_tree.nodes:
                group_node_key = f"{group_node.name}_{id(group_node)}"
                if group_node_key not in current_path:
                    search_node(group_node, node.node_tree, depth + 1, current_path)
        
        # Search all input sockets of this node
        for input_socket in node.inputs:
            if input_socket.is_linked:
                socket_key = f"{input_socket.name}_{id(input_socket)}"
                if socket_key in visited_sockets:
                    continue
                visited_sockets[socket_key] = True
                
                for link in input_socket.links:
                    from_node = link.from_node
                    from_key = f"{from_node.name}_{id(from_node)}"
                    if from_key not in current_path:
                        search_node(from_node, node_tree, depth + 1, current_path)
    
    start_node_tree = None
    if socket.is_linked:
        start_node = socket.links[0].from_node
        if material and material.node_tree:
            start_node_tree = _find_node_tree_for_node(start_node, material.node_tree)
        
        for link in socket.links:
            search_node(link.from_node, start_node_tree, 0)
    
    if not max_resolution and debug_nodes:
        debug_print(f"Debug - No textures found, visited {len(visited_nodes.keys())} nodes:")
        for node_info in debug_nodes[:15]:
            debug_print(f"{node_info}")
        if len(debug_nodes) > 15:
            debug_print(f"... and {len(debug_nodes) - 15} more")
    
    return max_resolution


def _build_group_instance_map(node_tree, group_map, parent_tree=None):
    """
    Build a map of node_tree -> list of (group_node, parent_tree) instances.
    """
    if parent_tree is None:
        parent_tree = node_tree
    
    for node in node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree is not None:
            if node.node_tree not in group_map:
                group_map[node.node_tree] = []
            group_map[node.node_tree].append((node, parent_tree))
            
            _build_group_instance_map(node.node_tree, group_map, parent_tree)


def _find_node_tree_for_node(node, material_tree):
    """
    Find which node tree a node belongs to.
    """
    for n in material_tree.nodes:
        if n == node:
            return material_tree
    
    for n in material_tree.nodes:
        if n.type == 'GROUP' and n.node_tree is not None:
            result = _find_node_tree_for_node(node, n.node_tree)
            if result:
                return result
    
    return None

