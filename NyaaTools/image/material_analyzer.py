# Version Auto

"""Material analysis utilities for extracting texture information from Blender materials."""

import bpy
import math
from typing import Optional, Tuple, Dict, Set


def find_principled_bsdf(material: bpy.types.Material) -> Optional[Dict]:
    """
    Find the Principled BSDF node connected to the material output.

    Args:
        material: The Blender material to search

    Returns:
        Dict with 'material_output' (Material Output node), 'principled_bsdf' (Principled BSDF), 'tree_stack' (list of trees), or None
    """
    if not material.use_nodes:
        return None

    node_tree = material.node_tree
    if not node_tree:
        return None

    return _find_principled_bsdf_in_tree(node_tree)


def _find_principled_bsdf_in_tree(node_tree: bpy.types.NodeTree) -> Optional[Dict]:
    """
    Find the Principled BSDF node connected to the material output.

    Args:
        node_tree: The node tree to search

    Returns:
        Dict with 'material_output' (Material Output node), 'principled_bsdf' (Principled BSDF), 'tree_stack' (list of trees), or None
    """

    def debug_print(*msgs):
        print("        ", *msgs)
        return

    if not node_tree:
        return None

    # Find material output node
    output_node = None
    for node in node_tree.nodes:
        if node.type == "OUTPUT_MATERIAL" and node.is_active_output:
            output_node = node
            break

    # Fallback to any output if no active output found
    if not output_node:
        for node in node_tree.nodes:
            if node.type == "OUTPUT_MATERIAL":
                output_node = node
                break

    if not output_node:
        debug_print("No Material Output node found in tree")
        return None

    surface_input = output_node.inputs.get("Surface")
    if not surface_input or not surface_input.is_linked:
        debug_print("Material Output has no connected Surface input")
        return None

    visited_nodes = set()
    tree_stack = [node_tree]  # Start with root tree
    result = _trace_to_principled_bsdf(
        surface_input.links[0].from_node, visited_nodes, tree_stack
    )
    if result:
        return {
            "material_output": output_node,
            "principled_bsdf": result,
            "tree_stack": tree_stack,
        }
    return None


def _trace_to_principled_bsdf(
    node: bpy.types.Node, visited_nodes: set, tree_stack: list
) -> Optional[bpy.types.ShaderNode]:
    """
    Trace through the node tree to find a Principled BSDF node.

    Args:
        node: Current node to examine
        visited_nodes: Set of already visited nodes to prevent infinite loops
        tree_stack: List of trees we've traversed through

    Returns:
        Principled BSDF node if found, None otherwise
    """

    def debug_print(*msgs):
        print("        ", *msgs)
        return

    # Prevent infinite loops
    node_id = str(node.name) + str(id(node))
    if node_id in visited_nodes:
        return None
    visited_nodes.add(node_id)

    if node.type == "BSDF_PRINCIPLED":
        return node

    if node.type == "GROUP":
        if not node.node_tree:
            return None

        # Add this group's tree to the stack
        tree_stack.append(node.node_tree)

        # Find group output node
        group_output = None
        for group_node in node.node_tree.nodes:
            if group_node.type == "GROUP_OUTPUT" and group_node.is_active_output:
                group_output = group_node
                break

        if not group_output:
            for group_node in node.node_tree.nodes:
                if group_node.type == "GROUP_OUTPUT":
                    group_output = group_node
                    break

        if not group_output:
            return None

        # Trace from group output inputs
        for input_socket in group_output.inputs:
            if input_socket.is_linked:
                for link in input_socket.links:
                    result = _trace_to_principled_bsdf(
                        link.from_node, visited_nodes, tree_stack
                    )
                    if result:
                        return result

    elif node.type in ["MIX_SHADER", "ADD_SHADER", "SHADER_TO_RGB"]:
        # Check all shader inputs
        for input_socket in node.inputs:
            if input_socket.is_linked:
                for link in input_socket.links:
                    result = _trace_to_principled_bsdf(
                        link.from_node, visited_nodes, tree_stack
                    )
                    if result:
                        return result

    else:
        # Check all inputs for other node types
        for input_socket in node.inputs:
            if input_socket.is_linked:
                for link in input_socket.links:
                    result = _trace_to_principled_bsdf(
                        link.from_node, visited_nodes, tree_stack
                    )
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


def _round_to_power_of_2(value: int) -> int:
    """
    Round a value to the nearest power of 2.

    Args:
        value: The value to round

    Returns:
        The nearest power of 2 (e.g., 1000 -> 1024, 500 -> 512)
    """
    if value <= 0:
        return 1

    # Find the nearest power of 2
    power = math.log2(value)
    lower_power = 2 ** int(power)
    upper_power = 2 ** (int(power) + 1)

    # Return the closer one
    if value - lower_power < upper_power - value:
        return lower_power
    else:
        return upper_power


def detect_best_resolution(
    socket: bpy.types.NodeSocket, tree_stack: list
) -> Tuple[int, int]:
    """
    Detect the best resolution for baking by analyzing connected textures.

    Args:
        socket: The input socket to search from
        tree_stack: List of trees that are part of the active material path

    Returns:
        Tuple of (width, height) for the highest resolution texture found
    """
    if not socket or not socket.is_linked:
        return (512, 512)

    visited_nodes = set()
    max_dimensions = [0, 0]  # [width, height] - mutable container

    # Start from the socket's tree
    current_tree = socket.id_data

    # Follow the first link backwards
    for link in socket.links:
        from_node = link.from_node
        _detect_best_resolution_recursion(
            from_node, current_tree, tree_stack, visited_nodes, max_dimensions, None
        )

    # Round to nearest power of 2 for optimal texture performance
    if max_dimensions[0] > 0 and max_dimensions[1] > 0:
        final_width = _round_to_power_of_2(max_dimensions[0])
        final_height = _round_to_power_of_2(max_dimensions[1])
        return (final_width, final_height)

    # Default to 512x512 if no textures found
    return (512, 512)


def _detect_best_resolution_recursion(
    node: bpy.types.Node,
    current_tree: bpy.types.NodeTree,
    tree_stack: list,
    visited_nodes: set,
    max_dimensions: list,
    parent_group_node: Optional[bpy.types.Node] = None,
) -> None:
    """
    Recursively search for texture nodes within the tree stack constraint.

    Args:
        node: Current node to examine
        current_tree: Tree we're currently searching in
        tree_stack: List of valid trees to search in
        visited_nodes: Set of (node_id, tree_id) tuples to prevent infinite loops
        max_dimensions: [max_width, max_height] - mutable list to track maximum dimensions
        parent_group_node: The GROUP node instance we entered from (None if not entered via a group)
    """
    # Material Tree (Shader Nodetree)
    # ├── Image Texture (8192x8192) ← TARGET TEXTURE
    # └── "Scene Shader" Group
    #     ├── Group Input ← Multiple inputs connected to same texture
    #     ├── Group Input ← Multiple inputs connected to same texture
    #     ├── Group Input ← Multiple inputs connected to same texture
    #     └── "NyaaPBRToon" Group
    #         ├── Group Input ← Normal Map input
    #         └── Normal Map ← ORIGIN (where we started)

    # Create unique key for this node in this tree context
    node_key = (f"{node.name}_{id(node)}", id(current_tree))
    if node_key in visited_nodes:
        return
    visited_nodes.add(node_key)

    # Check if this is a texture node
    if node.type == "TEX_IMAGE" and node.image and not node.mute:
        width, height = node.image.size[0], node.image.size[1]
        if width > max_dimensions[0]:
            max_dimensions[0] = width
        if height > max_dimensions[1]:
            max_dimensions[1] = height

    # Handle GROUP nodes - only enter if the group's tree is in our tree_stack
    elif node.type == "GROUP" and node.node_tree and node.node_tree in tree_stack:
        # Enter the group, passing this GROUP node instance as parent_group_node
        new_tree = node.node_tree
        for group_node in new_tree.nodes:
            if group_node.type == "GROUP_OUTPUT":
                # Search from group output inputs
                for input_socket in group_node.inputs:
                    if input_socket.is_linked:
                        for link in input_socket.links:
                            _detect_best_resolution_recursion(
                                link.from_node,
                                new_tree,
                                tree_stack,
                                visited_nodes,
                                max_dimensions,
                                node,  # Pass the GROUP node instance we entered from
                            )
                break

    # Handle GROUP_INPUT nodes - exit to parent tree
    elif node.type == "GROUP_INPUT" and current_tree in tree_stack:
        # Only follow inputs from the specific GROUP node instance we entered from
        if parent_group_node:
            parent_tree = parent_group_node.id_data
            # Follow input sockets of the specific parent group node instance
            for input_socket in parent_group_node.inputs:
                if input_socket.is_linked:
                    for link in input_socket.links:
                        _detect_best_resolution_recursion(
                            link.from_node,
                            parent_tree,
                            tree_stack,
                            visited_nodes,
                            max_dimensions,
                            None,  # Reset parent_group_node when exiting to parent
                        )
        else:
            # Fallback: if parent_group_node is None, use old behavior
            # This shouldn't happen in normal traversal, but kept for safety
            try:
                current_index = tree_stack.index(current_tree)
                if current_index > 0:
                    parent_tree = tree_stack[current_index - 1]
                    # Find all GROUP nodes in parent tree that use current_tree
                    for group_node in parent_tree.nodes:
                        if (
                            group_node.type == "GROUP"
                            and group_node.node_tree == current_tree
                        ):
                            # Follow all input sockets of this group node
                            for input_socket in group_node.inputs:
                                if input_socket.is_linked:
                                    for link in input_socket.links:
                                        _detect_best_resolution_recursion(
                                            link.from_node,
                                            parent_tree,
                                            tree_stack,
                                            visited_nodes,
                                            max_dimensions,
                                            None,
                                        )
            except ValueError:
                pass  # current_tree not in tree_stack, skip

    # For all other nodes, follow input sockets backwards
    else:
        for input_socket in node.inputs:
            if input_socket.is_linked:
                for link in input_socket.links:
                    _detect_best_resolution_recursion(
                        link.from_node,
                        current_tree,
                        tree_stack,
                        visited_nodes,
                        max_dimensions,
                        parent_group_node,  # Preserve parent_group_node through other nodes
                    )
