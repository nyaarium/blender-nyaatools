"""Node graph state tracking for safe socket manipulation during baking."""

import bpy
from typing import List, Tuple


class NodeGraphState:
    """
    Tracks node graph modifications during baking to ensure safe restoration.
    
    Inspired by the renamer pattern, this class safely manages:
    - Detaching original socket connections
    - Creating temporary nodes
    - Restoring original state after baking
    """
    
    def __init__(self, material: bpy.types.Material, root_tree: bpy.types.NodeTree, principled_tree: bpy.types.NodeTree):
        """
        Initialize state tracker for a material's node graph.
        
        Args:
            material: The material being modified
            root_tree: Root material node tree
            principled_tree: Node tree containing the Principled BSDF (may be same as root_tree)
        """
        self.material = material
        self.root_tree = root_tree
        self.principled_tree = principled_tree
        
        # Track detached connections (store as REFERENCES)
        # Format: [(node_tree, from_node_ref, from_socket_name, to_node_ref, to_socket_name), ...]
        self.detached_links: List[Tuple[bpy.types.NodeTree, bpy.types.Node, str, bpy.types.Node, str]] = []
        
        # Track temporary nodes we created (store REFERENCE for deletion)
        # Format: [(node_tree, node_ref), ...]
        self.temp_nodes: List[Tuple[bpy.types.NodeTree, bpy.types.Node]] = []
    
    def detach_socket(self, socket: bpy.types.NodeSocket) -> None:
        """
        Safely detach a socket, recording original connections for restoration.
        
        Args:
            socket: The socket to detach (removes all incoming connections)
        """
        if not socket.is_linked:
            return
        
        # Record all incoming connections before detaching
        for link in list(socket.links):
            self.detached_links.append((
                link.from_node.id_data,  # node_tree
                link.from_node,
                link.from_socket.name,
                link.to_node,
                link.to_socket.name
            ))
        
        # Remove all connections to this socket
        socket.id_data.links.remove(link)
    
    def connect_sockets(self, node_tree: bpy.types.NodeTree, from_node: bpy.types.Node, 
                       from_socket_name: str, to_node: bpy.types.Node, to_socket_name: str, 
                       *debug_parts) -> None:
        """
        Create a new connection, removing any existing ones on the target.
        Stores node references directly for restoration.
        
        Args:
            node_tree: The node tree containing the nodes
            from_node: Source node
            from_socket_name: Name of source socket
            to_node: Target node  
            to_socket_name: Name of target socket
            *debug_parts: Optional debug message parts for logging
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

        from_socket = from_node.outputs.get(from_socket_name)
        to_socket = to_node.inputs.get(to_socket_name)
        
        if not from_socket or not to_socket:
            return
        
        # Detach any existing connections to the target socket
        self.detach_socket(to_socket)
        
        # Create the new connection
        node_tree.links.new(from_socket, to_socket)
    
    def add_node(self, node_tree: bpy.types.NodeTree, node_type: str) -> bpy.types.Node:
        """
        Create and track a temporary node.
        
        Args:
            node_tree: The node tree to add the node to
            node_type: Blender node type (e.g., 'ShaderNodeBsdfDiffuse')
            
        Returns:
            The created node reference
        """
        node = node_tree.nodes.new(node_type)
        self.temp_nodes.append((node_tree, node))
        return node
    
    def restore(self) -> None:
        """
        Delete temp nodes and restore original connections.
        
        This method:
        1. Deletes all temporary nodes (with try-catch for already-deleted nodes)
        2. Restores all original socket connections
        """
        # Delete temporary nodes
        for node_tree, node_ref in self.temp_nodes:
            try:
                if node_ref and node_ref.name in node_tree.nodes:
                    node_tree.nodes.remove(node_ref)
            except:
                # Node already deleted or invalid - don't care
                pass
        
        # Restore original connections
        for node_tree, from_node, from_socket_name, to_node, to_socket_name in self.detached_links:
            try:
                from_socket = from_node.outputs.get(from_socket_name)
                to_socket = to_node.inputs.get(to_socket_name)
                
                if from_socket and to_socket:
                    node_tree.links.new(from_socket, to_socket)
            except:
                # Connection already exists or nodes invalid - don't care
                pass
        
        # Clear tracking data
        self.detached_links.clear()
        self.temp_nodes.clear()
    
    def debug_print_state(self) -> None:
        """Print current state for debugging purposes."""
        print(f"NodeGraphState for material '{self.material.name}':")
        print(f"  Detached links: {len(self.detached_links)}")
        for i, (tree, from_node, from_socket, to_node, to_socket) in enumerate(self.detached_links):
            print(f"    {i}: {from_node.name}.{from_socket} -> {to_node.name}.{to_socket}")
        print(f"  Temp nodes: {len(self.temp_nodes)}")
        for i, (tree, node) in enumerate(self.temp_nodes):
            print(f"    {i}: {node.name} ({node.type})")
