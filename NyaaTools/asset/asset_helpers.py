"""
Asset helper functions for UI and selection context.
"""

import bpy


def get_asset_description(obj, export_profile=None) -> str:
    """
    Get a human-readable description of an asset.

    Uses cached is_humanoid flag from nyaa_asset to avoid expensive bone analysis.

    Args:
        obj: The asset host object
        export_profile: Optional export profile to check for export_static flag

    Returns:
        "Humanoid asset" if armature marked as humanoid
        "Rigged asset" if armature but not humanoid
        "Static asset" if mesh-hosted asset or export_static is enabled
    """
    if obj is None:
        return ""
    if obj.type == "ARMATURE":
        # Check if current profile exports as static
        if export_profile and export_profile.export_static:
            return "Static asset"
        # Use cached flag instead of recomputing every draw
        if hasattr(obj, "nyaa_asset") and obj.nyaa_asset.is_humanoid:
            return "Humanoid asset"
        return "Rigged asset"
    return "Static asset"


def find_asset_for_mesh(mesh_obj):
    """
    Find which asset(s) a mesh belongs to.

    Args:
        mesh_obj: The mesh object to check

    Returns:
        List of (asset_host, layer_name) tuples for assets that reference this mesh.
    """
    if mesh_obj is None or mesh_obj.type != "MESH":
        return []

    results = []
    for obj in bpy.data.objects:
        if not hasattr(obj, "nyaa_asset"):
            continue
        if not obj.nyaa_asset.is_asset:
            continue

        for entry in obj.nyaa_asset.meshes:
            if entry.mesh_object == mesh_obj:
                results.append((obj, entry.layer_name))
                break

    return results


def get_armature_from_mesh_modifiers(mesh_obj):
    """
    Find the first armature referenced by the mesh's modifiers.

    Args:
        mesh_obj: The mesh object to check

    Returns:
        The first armature object found in modifiers, or None
    """
    if mesh_obj is None or mesh_obj.type != "MESH":
        return None

    for mod in mesh_obj.modifiers:
        if mod.type == "ARMATURE" and mod.object:
            return mod.object

    return None


def get_available_armatures_for_mesh(mesh_obj):
    """
    Get armatures that could be associated with a mesh.

    Prioritizes armatures from the mesh's modifiers, then lists all others.

    Args:
        mesh_obj: The mesh object

    Returns:
        list of tuples: (armature, is_already_asset, is_from_modifier)
    """
    results = []
    modifier_armature = get_armature_from_mesh_modifiers(mesh_obj)

    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        is_asset = obj.nyaa_asset.is_asset if hasattr(obj, "nyaa_asset") else False
        is_from_modifier = obj == modifier_armature
        results.append((obj, is_asset, is_from_modifier))

    # Sort: modifier armature first, then by name
    results.sort(key=lambda x: (not x[2], x[0].name))

    return results


def get_layer_name_collisions(asset_host):
    """
    Check if any layer names would collide with existing object names.

    Excludes objects in the __Export__ collection since those get cleared.

    Args:
        asset_host: The asset host object

    Returns:
        List of (layer_name, conflicting_object_name) tuples
    """
    if not hasattr(asset_host, "nyaa_asset") or not asset_host.nyaa_asset.is_asset:
        return []

    cfg = asset_host.nyaa_asset

    # Collect layer names from asset
    layer_names = set()

    # For mesh-hosted assets, the host mesh's layer name
    if asset_host.type == "MESH":
        for entry in cfg.meshes:
            if entry.mesh_object == asset_host:
                layer_names.add(entry.layer_name)
                break
        else:
            layer_names.add("Base")  # Default if not in meshes list

    # All layer names from meshes list
    for entry in cfg.meshes:
        if entry.mesh_object:
            layer_names.add(entry.layer_name)

    # Get objects in __Export__ collection (these will be cleared)
    export_collection = bpy.data.collections.get("__Export__")
    export_objects = set()
    if export_collection:
        export_objects = {obj.name for obj in export_collection.objects}

    # Get meshes that are part of this asset (these are allowed to share names)
    asset_mesh_names = set()
    for entry in cfg.meshes:
        if entry.mesh_object:
            asset_mesh_names.add(entry.mesh_object.name)
    if asset_host.type == "MESH":
        asset_mesh_names.add(asset_host.name)

    # Check for collisions
    collisions = []
    for layer_name in layer_names:
        if layer_name in bpy.data.objects:
            obj = bpy.data.objects[layer_name]
            # Skip if object is in __Export__ (will be cleared)
            if obj.name in export_objects:
                continue
            # Skip if object is part of this asset
            if obj.name in asset_mesh_names:
                continue
            collisions.append((layer_name, obj.name))

    return collisions
