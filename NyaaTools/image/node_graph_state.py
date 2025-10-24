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
        # Validate node references are still valid
        if not from_node or not to_node:
            print(f"Warning: Invalid node references in connect_sockets")
            return
            
        # Get fresh node references to ensure they're still valid
        from_node_fresh = node_tree.nodes.get(from_node.name)
        to_node_fresh = node_tree.nodes.get(to_node.name)
        
        if not from_node_fresh or not to_node_fresh:
            print(f"Warning: Nodes not found in tree: {from_node.name if from_node else 'None'}, {to_node.name if to_node else 'None'}")
            return
        
        from_socket = from_node_fresh.outputs.get(from_socket_name)
        to_socket = to_node_fresh.inputs.get(to_socket_name)
        
        if not from_socket or not to_socket:
            return
        
        # Check if either node is temporary - if so, don't track for restoration
        from_is_temp = any(node_ref == from_node for _, node_ref in self.temp_nodes)
        to_is_temp = any(node_ref == to_node for _, node_ref in self.temp_nodes)
        
        if not from_is_temp and not to_is_temp:
            # Both permanent - detach and track
            self.detach_socket(to_socket)
        elif from_is_temp and to_is_temp:
            # Both temporary - just remove existing connections without tracking
            for link in list(to_socket.links):
                node_tree.links.remove(link)
        elif to_is_temp:
            # Target is temporary - just remove existing connections without tracking
            for link in list(to_socket.links):
                node_tree.links.remove(link)
        elif from_is_temp:
            # Source is temporary - still need to detach target socket
            self.detach_socket(to_socket)
        
        # Create the new connection using fresh node references
        try:
            node_tree.links.new(from_socket, to_socket)
        except Exception as e:
            print(f"Warning: Failed to create connection {from_node_fresh.name}.{from_socket_name} -> {to_node_fresh.name}.{to_socket_name}: {e}")
    
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

        # Disconnect all temporary node connections
        for node_tree, node_ref in self.temp_nodes:
            try:
                if not node_ref:
                    continue
                    
                # Get fresh node reference to ensure it's still valid
                node_ref_fresh = node_tree.nodes.get(node_ref.name)
                if not node_ref_fresh:
                    continue
                    
                # Disconnect all inputs and outputs of the temporary node
                for input_socket in node_ref_fresh.inputs:
                    if input_socket.is_linked:
                        for link in list(input_socket.links):
                            node_tree.links.remove(link)
                for output_socket in node_ref_fresh.outputs:
                    if output_socket.is_linked:
                        for link in list(output_socket.links):
                            node_tree.links.remove(link)
            except Exception as e:
                # Node already deleted or invalid - don't care
                print(f"Warning: Failed to disconnect temp node {node_ref.name if node_ref else 'None'}: {e}")
                pass
        
        # Delete temporary nodes
        for node_tree, node_ref in self.temp_nodes:
            try:
                if not node_ref:
                    continue
                    
                # Get fresh node reference to ensure it's still valid
                node_ref_fresh = node_tree.nodes.get(node_ref.name)
                if node_ref_fresh:
                    node_tree.nodes.remove(node_ref_fresh)
            except Exception as e:
                # Node already deleted or invalid - don't care
                print(f"Warning: Failed to remove temp node {node_ref.name if node_ref else 'None'}: {e}")
                pass
        
        # Restore original connections
        for node_tree, from_node, from_socket_name, to_node, to_socket_name in self.detached_links:
            try:
                # Validate that nodes still exist and are valid
                if not from_node or not to_node:
                    continue
                
                # Check if nodes are still in their respective trees
                if from_node.name not in node_tree.nodes or to_node.name not in node_tree.nodes:
                    continue
                
                # Get fresh node references to ensure they're still valid
                from_node_ref = node_tree.nodes.get(from_node.name)
                to_node_ref = node_tree.nodes.get(to_node.name)
                
                if not from_node_ref or not to_node_ref:
                    continue
                
                from_socket = from_node_ref.outputs.get(from_socket_name)
                to_socket = to_node_ref.inputs.get(to_socket_name)

                if from_socket and to_socket:
                    node_tree.links.new(from_socket, to_socket)
            except Exception as e:
                # Connection already exists or nodes invalid - don't care
                print(f"Warning: Failed to restore connection {from_node.name if from_node else 'None'}.{from_socket_name} -> {to_node.name if to_node else 'None'}.{to_socket_name}: {e}")
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
