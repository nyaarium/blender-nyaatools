"""Material analysis utilities for extracting texture information from Blender materials."""

import bpy
import math
from typing import Optional, Tuple, List, Dict


def find_all_principled_bsdfs(
    material: bpy.types.Material,
) -> List[Dict]:
    """
    Find all Principled BSDF nodes in a material, including inside node groups.

    Args:
        material: The Blender material to search

    Returns:
        List of dicts, each with:
            - "node": The Principled BSDF node
            - "tree": The NodeTree containing the node
        Returns empty list if no nodes found.
    """
    if not material or not material.use_nodes:
        return []

    node_tree = material.node_tree
    if not node_tree:
        return []

    return _scan_for_principled_bsdfs(node_tree)


def _scan_for_principled_bsdfs(
    node_tree: bpy.types.NodeTree,
    visited: set = None,
) -> List[Dict]:
    """
    Recursively scan a node tree for all Principled BSDF nodes.

    Args:
        node_tree: The node tree to search
        visited: Set of visited tree names (prevents infinite recursion)

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
            group_results = _scan_for_principled_bsdfs(node.node_tree, visited)
            results.extend(group_results)

    return results


def build_tree_stack(material: bpy.types.Material) -> List[bpy.types.NodeTree]:
    """
    Build a list of all node trees in a material (root + all nested groups).

    Used for resolution detection which needs to traverse across tree boundaries.

    Args:
        material: The Blender material

    Returns:
        List of NodeTrees, starting with root, then all nested groups
    """
    if not material or not material.use_nodes or not material.node_tree:
        return []

    tree_stack = [material.node_tree]
    visited = {material.node_tree.name}

    def collect_groups(node_tree: bpy.types.NodeTree):
        for node in node_tree.nodes:
            if node.type == "GROUP" and node.node_tree:
                if node.node_tree.name not in visited:
                    visited.add(node.node_tree.name)
                    tree_stack.append(node.node_tree)
                    collect_groups(node.node_tree)

    collect_groups(material.node_tree)
    return tree_stack


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
