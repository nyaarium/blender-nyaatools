"""
Shared layer merge functionality for asset export.

Used by both file-based export and collection-based export.
"""

import bpy

from ..mesh.cleanup_mesh import cleanup_mesh
from ..common.renamer_rename import rename_object
from .merge_onto_layer import merge_onto_layer
from .._external.przemir.helper import applyModifierForObjectWithShapeKeys
from .asset_lookup import get_asset_meshes_by_layer


def get_asset_collider_meshes(asset_host):
    """
    Get collider meshes from asset's PropertyGroup.

    Args:
        asset_host: The asset host object (armature or mesh)

    Returns:
        list: List of (mesh_object, entry) tuples for collider meshes
    """
    result = []

    if not hasattr(asset_host, "nyaa_asset") or not asset_host.nyaa_asset.is_asset:
        return result

    cfg = asset_host.nyaa_asset
    for entry in cfg.meshes:
        if entry.mesh_object and entry.is_ue_collider:
            result.append((entry.mesh_object, entry))

    return result


def get_asset_non_collider_meshes_by_layer(asset_host):
    """
    Get non-collider meshes grouped by layer from asset's PropertyGroup.

    Args:
        asset_host: The asset host object (armature or mesh)

    Returns:
        dict: {layer_name: {mesh_name: mesh_object}} excluding colliders
    """
    result = {}

    if not hasattr(asset_host, "nyaa_asset") or not asset_host.nyaa_asset.is_asset:
        # Fallback to legacy function for non-asset hosts
        return get_asset_meshes_by_layer(asset_host)

    cfg = asset_host.nyaa_asset

    # For mesh-hosted assets, find host's layer name from cfg.meshes
    if asset_host.type == "MESH":
        host_layer = "Base"
        host_is_collider = False
        for entry in cfg.meshes:
            if entry.mesh_object == asset_host:
                host_layer = entry.layer_name
                host_is_collider = entry.is_ue_collider
                break
        # Only add if not a collider
        if not host_is_collider:
            result[host_layer] = {asset_host.name: asset_host}

    # Add non-collider meshes from cfg.meshes
    for entry in cfg.meshes:
        if not entry.mesh_object:
            continue
        # Skip colliders
        if entry.is_ue_collider:
            continue
        # Skip if this is the host mesh itself (already added above)
        if asset_host.type == "MESH" and entry.mesh_object == asset_host:
            continue
        layer = entry.layer_name
        if layer not in result:
            result[layer] = {}
        result[layer][entry.mesh_object.name] = entry.mesh_object

    return result


def sort_mesh_elements_by_material(mesh_obj, debug_print=None):
    """
    Sort mesh elements by material for better game engine compatibility.

    This helps Unity and other engines that may have issues with unsorted mesh data.
    Must enter Edit Mode and Face selection mode to use the sort operator.

    Args:
        mesh_obj: The mesh object to sort
        debug_print: Optional debug print function
    """
    if debug_print is None:

        def debug_print(*args):
            pass

    if mesh_obj.type != "MESH":
        return

    # Store current mode
    original_mode = bpy.context.object.mode if bpy.context.object else "OBJECT"

    try:
        # Select and activate the mesh
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        mesh_obj.select_set(True)
        bpy.context.view_layer.objects.active = mesh_obj

        # Enter Edit Mode
        bpy.ops.object.mode_set(mode="EDIT")

        # Switch to Face selection mode (required for sort by material)
        bpy.ops.mesh.select_mode(type="FACE")

        # Select all faces
        bpy.ops.mesh.select_all(action="SELECT")

        # Sort elements by material
        bpy.ops.mesh.sort_elements(type="MATERIAL", elements={"FACE"})

        debug_print(f"🔀 Sorted mesh elements by material: {mesh_obj.name}")

    except RuntimeError as e:
        debug_print(f"⚠️ Could not sort mesh elements: {e}")

    finally:
        # Return to Object Mode
        bpy.ops.object.mode_set(mode="OBJECT")


def merge_single_layer(
    layer_name,
    layer_meshes,
    target_collection,
    armature_copy=None,
    is_static_export=False,
    debug_print=None,
):
    """
    Copy and merge meshes for a single layer into a target collection.

    Args:
        layer_name: Name of the layer
        layer_meshes: Dict of {mesh_name: mesh_object} for this layer
        target_collection: Collection to link copied objects to
        armature_copy: Optional copied armature (None for static/mesh-hosted assets)
        is_static_export: If True, apply all modifiers including armature. If False, skip armature modifiers.
        debug_print: Optional debug print function

    Returns:
        tuple: (merged_mesh_object, unrename_info)
            - merged_mesh_object: The resulting merged mesh object
            - unrename_info: list of rename info for restoration
    """
    if debug_print is None:

        def debug_print(*args):
            pass

    unrename_info = []
    first_visit = True

    for mesh_name in layer_meshes:
        mesh = layer_meshes[mesh_name]

        mesh_copy = mesh.copy()
        mesh_copy.data = mesh.data.copy()
        layer_meshes[mesh_name] = mesh_copy
        target_collection.objects.link(mesh_copy)

        # Clear nyaa_asset config on copy (don't want exported objects marked as assets)
        if hasattr(mesh_copy, "nyaa_asset"):
            mesh_copy.nyaa_asset.is_asset = False
            mesh_copy.nyaa_asset.asset_name = ""
            mesh_copy.nyaa_asset.meshes.clear()
            mesh_copy.nyaa_asset.export_profiles.clear()
            mesh_copy.nyaa_asset.bake_images.clear()

        if first_visit:
            unrename_info.extend(rename_object(mesh_copy, layer_name))
            first_visit = False
            debug_print(f"📦 Created layer: {layer_name}")

        # Apply all modifiers and shape keys before merging
        if mesh_copy.type == "MESH":
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action="DESELECT")
            mesh_copy.select_set(True)
            bpy.context.view_layer.objects.active = mesh_copy

            # Apply all modifiers (except armature for rigged exports)
            if mesh_copy.data.shape_keys:
                mesh_copy.active_shape_key_index = 0
                # Apply all modifiers using Przemir (handles shape keys)
                # Filter out armature modifiers for rigged exports
                modifier_names = [
                    mod.name
                    for mod in mesh_copy.modifiers
                    if is_static_export or mod.type != "ARMATURE"
                ]
                if modifier_names:
                    try:
                        success, error_info = applyModifierForObjectWithShapeKeys(
                            bpy.context, modifier_names, False
                        )
                        if not success:
                            raise RuntimeError(
                                f"Failed to apply modifiers on '{mesh_copy.name}': {error_info or 'Unknown error'}"
                            )
                        debug_print(
                            f"Applied all modifiers and shape keys to {mesh_name} before merge"
                        )
                    except RuntimeError as e:
                        raise RuntimeError(
                            f"Failed to apply modifiers on '{mesh_copy.name}': {e}"
                        )
            else:
                # No shape keys, apply modifiers normally
                for mod in list(mesh_copy.modifiers):
                    # Skip armature modifiers for rigged exports
                    if not is_static_export and mod.type == "ARMATURE":
                        continue
                    
                    mod_name = mod.name
                    try:
                        bpy.ops.object.modifier_apply(modifier=mod_name)
                        debug_print(
                            f"Applied modifier {mod_name} to {mesh_name} before merge"
                        )
                    except RuntimeError as e:
                        raise RuntimeError(
                            f"Failed to apply modifier '{mod_name}' on '{mesh_copy.name}': {e}"
                        )

        merge_onto_layer(layer_name, mesh_copy, armature_copy)
        debug_print(f"   Merged: {mesh_name}")

    # Get the merged result (named after the layer)
    merged_obj = None
    for obj in target_collection.objects:
        if obj.name == layer_name and obj.type == "MESH":
            merged_obj = obj
            break

    if merged_obj:
        cleanup_mesh(merged_obj)
        sort_mesh_elements_by_material(merged_obj, debug_print)
        debug_print(f"✅ Cleaned up layer: {layer_name}")

    return merged_obj, unrename_info


def merge_asset_layers(
    asset_host,
    target_collection,
    armature_copy=None,
    include_colliders=False,
    debug_print=None,
):
    """
    Copy and merge meshes by layer into a target collection.

    This is the core merge logic shared between file export and collection export.

    Args:
        asset_host: The asset host object (armature or mesh)
        target_collection: Collection to link copied objects to
        armature_copy: Optional copied armature (None for static/mesh-hosted assets)
        include_colliders: If True, also process UCX collider meshes
        debug_print: Optional debug print function

    Returns:
        tuple: (merged_layer_objects, collider_objects, unrename_info)
            - merged_layer_objects: dict {layer_name: merged_mesh_object}
            - collider_objects: list of collider mesh objects (empty if include_colliders=False)
            - unrename_info: list of rename info for restoration
    """
    if debug_print is None:

        def debug_print(*args):
            pass

    # Get non-collider meshes only
    asset_meshes_layers = get_asset_non_collider_meshes_by_layer(asset_host)
    unrename_info = []
    merged_layer_objects = {}
    collider_objects = []

    for layer_name in asset_meshes_layers:
        layer = asset_meshes_layers[layer_name]
        first_visit = True

        for mesh_name in layer:
            mesh = layer[mesh_name]

            mesh_copy = mesh.copy()
            mesh_copy.data = mesh.data.copy()
            layer[mesh_name] = mesh_copy
            target_collection.objects.link(mesh_copy)

            # Clear nyaa_asset config on copy (don't want exported objects marked as assets)
            if hasattr(mesh_copy, "nyaa_asset"):
                mesh_copy.nyaa_asset.is_asset = False
                mesh_copy.nyaa_asset.asset_name = ""
                mesh_copy.nyaa_asset.meshes.clear()
                mesh_copy.nyaa_asset.export_profiles.clear()
                mesh_copy.nyaa_asset.bake_images.clear()

            if first_visit:
                unrename_info.extend(rename_object(mesh_copy, layer_name))
                first_visit = False
                debug_print(f"📦 Created layer: {layer_name}")

            merge_onto_layer(layer_name, mesh_copy, armature_copy)
            debug_print(f"   Merged: {mesh_name}")

        # Get the merged result (named after the layer)
        merged_obj = None
        for obj in target_collection.objects:
            if obj.name == layer_name and obj.type == "MESH":
                merged_obj = obj
                break

        if merged_obj:
            cleanup_mesh(merged_obj)
            sort_mesh_elements_by_material(merged_obj, debug_print)
            merged_layer_objects[layer_name] = merged_obj
            debug_print(f"✅ Cleaned up layer: {layer_name}")

    # Process colliders if requested
    if include_colliders:
        collider_objs, collider_unrename = process_collider_meshes(
            asset_host, target_collection, debug_print
        )
        collider_objects.extend(collider_objs)
        unrename_info.extend(collider_unrename)

    return merged_layer_objects, collider_objects, unrename_info


def process_collider_meshes(asset_host, target_collection, debug_print=None):
    """
    Process collider meshes for export.

    Each collider is:
    - Copied (not merged)
    - Renamed to UCX_{AssetName} or UCX_{AssetName}_{N}
    - Separated by loose parts
    - Material slots stripped

    Args:
        asset_host: The asset host object (armature or mesh)
        target_collection: Collection to link copied objects to
        debug_print: Optional debug print function

    Returns:
        tuple: (collider_objects, unrename_info)
            - collider_objects: list of collider mesh objects
            - unrename_info: list of rename info for restoration
    """
    if debug_print is None:

        def debug_print(*args):
            pass

    collider_meshes = get_asset_collider_meshes(asset_host)
    if not collider_meshes:
        return [], []

    cfg = asset_host.nyaa_asset
    asset_name = cfg.asset_name

    unrename_info = []
    collider_objects = []
    collider_index = 0

    debug_print(f"📦 Processing {len(collider_meshes)} collider(s)")

    for mesh, entry in collider_meshes:
        # Copy the mesh
        mesh_copy = mesh.copy()
        mesh_copy.data = mesh.data.copy()
        target_collection.objects.link(mesh_copy)

        # Clear nyaa_asset config on copy
        if hasattr(mesh_copy, "nyaa_asset"):
            mesh_copy.nyaa_asset.is_asset = False
            mesh_copy.nyaa_asset.asset_name = ""
            mesh_copy.nyaa_asset.meshes.clear()
            mesh_copy.nyaa_asset.export_profiles.clear()
            mesh_copy.nyaa_asset.bake_images.clear()

        # Rename to UCX pattern (avoid double UCX_)
        base_name = asset_name
        if base_name.upper().startswith("UCX_"):
            base_name = base_name[4:]

        if collider_index == 0:
            ucx_name = f"UCX_{base_name}"
        else:
            ucx_name = f"UCX_{base_name}_{collider_index}"

        unrename_info.extend(rename_object(mesh_copy, ucx_name))
        debug_print(f"   Collider: {mesh.name} → {ucx_name}")

        # Select and activate for operations
        bpy.ops.object.select_all(action="DESELECT")
        mesh_copy.select_set(True)
        bpy.context.view_layer.objects.active = mesh_copy

        # Separate by loose parts
        try:
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.separate(type="LOOSE")
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError:
            # May fail if mesh is already a single piece - that's fine
            bpy.ops.object.mode_set(mode="OBJECT")

        # Find all collider pieces (they may have been split)
        # After separate, the original is still selected, and new pieces are added
        collider_pieces = [
            obj
            for obj in target_collection.objects
            if obj.type == "MESH" and obj.name.startswith(ucx_name.split(".")[0])
        ]

        # Strip material slots from all pieces
        for piece in collider_pieces:
            bpy.context.view_layer.objects.active = piece
            while len(piece.material_slots) > 0:
                bpy.ops.object.material_slot_remove()

        collider_objects.extend(collider_pieces)
        collider_index += len(collider_pieces)

    debug_print(f"✅ Processed {len(collider_objects)} collider piece(s)")
    return collider_objects, unrename_info


def copy_armature_to_collection(
    asset_host, target_collection, armature_name="Armature", debug_print=None
):
    """
    Copy an armature to a target collection with transforms applied.

    Args:
        asset_host: The armature object to copy
        target_collection: Collection to link the copy to
        armature_name: Name to give the copied armature (default: "Armature")
        debug_print: Optional debug print function

    Returns:
        tuple: (armature_copy, unrename_info)
    """
    if debug_print is None:

        def debug_print(*args):
            pass

    armature_copy = asset_host.copy()
    armature_copy.data = asset_host.data.copy()
    target_collection.objects.link(armature_copy)

    # Clear nyaa_asset config on copy (don't want exported objects marked as assets)
    if hasattr(armature_copy, "nyaa_asset"):
        armature_copy.nyaa_asset.is_asset = False
        armature_copy.nyaa_asset.asset_name = ""
        armature_copy.nyaa_asset.is_humanoid = False
        armature_copy.nyaa_asset.meshes.clear()
        armature_copy.nyaa_asset.export_profiles.clear()
        armature_copy.nyaa_asset.bake_images.clear()

    # Apply transforms
    bpy.context.view_layer.objects.active = armature_copy
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    unrename_info = rename_object(armature_copy, armature_name)
    debug_print(f"📦 Copied armature: {armature_copy.name}")

    return armature_copy, unrename_info
