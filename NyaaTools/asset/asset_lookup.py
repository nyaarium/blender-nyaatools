"""
Asset lookup functions for finding assets and their data.
"""

import bpy


def get_asset_by_name(asset_name):
    """
    Find asset (armature or mesh) by asset_name using PropertyGroup system.

    Args:
        asset_name: The name of the asset to find

    Returns:
        The asset host object (armature or mesh) or None
    """
    for obj in bpy.data.objects:
        if hasattr(obj, "nyaa_asset") and obj.nyaa_asset.is_asset:
            if obj.nyaa_asset.asset_name == asset_name:
                return obj
    return None


def get_asset_meshes_by_layer(asset_host):
    """
    Get meshes grouped by layer from asset's PropertyGroup.

    Args:
        asset_host: The asset host object (armature or mesh)

    Returns:
        dict: {layer_name: {mesh_name: mesh_object}}
        For mesh-hosted assets, the host mesh uses its layer_name from cfg.meshes
        (or "Base" if not in cfg.meshes), plus any additional meshes.
    """
    result = {}

    if not hasattr(asset_host, "nyaa_asset") or not asset_host.nyaa_asset.is_asset:
        return result

    cfg = asset_host.nyaa_asset

    # For mesh-hosted assets, find host's layer name from cfg.meshes
    if asset_host.type == "MESH":
        host_layer = "Base"  # Default if not in cfg.meshes
        for entry in cfg.meshes:
            if entry.mesh_object == asset_host:
                host_layer = entry.layer_name
                break
        result[host_layer] = {asset_host.name: asset_host}

    # Add meshes from cfg.meshes (for both armature and mesh hosts)
    for entry in cfg.meshes:
        if not entry.mesh_object:
            continue
        # Skip if this is the host mesh itself (already added above)
        if asset_host.type == "MESH" and entry.mesh_object == asset_host:
            continue
        layer = entry.layer_name
        if layer not in result:
            result[layer] = {}
        result[layer][entry.mesh_object.name] = entry.mesh_object

    return result


def get_export_path_from_asset(asset_host):
    """
    Get export path from asset's active export profile.

    Args:
        asset_host: The asset host object (armature or mesh)

    Returns:
        The export path string or None
    """
    if not hasattr(asset_host, "nyaa_asset") or not asset_host.nyaa_asset.is_asset:
        return None

    cfg = asset_host.nyaa_asset
    if len(cfg.export_profiles) > 0 and 0 <= cfg.active_export_index < len(
        cfg.export_profiles
    ):
        return cfg.export_profiles[cfg.active_export_index].path

    return None
