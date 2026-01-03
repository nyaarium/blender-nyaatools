"""
Shared layer merge functionality for asset export.

Used by both file-based export (NyaaToolsAvatarMergeExport) and
collection-based export (export_collection).
"""

import bpy

from ..mesh.cleanup_mesh import cleanup_mesh
from ..common.renamer_rename import rename_object
from ..avatar.merge_onto_avatar_layer import merge_onto_avatar_layer

from .asset_lookup import get_asset_meshes_by_layer


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


def merge_asset_layers(
    asset_host, target_collection, armature_copy=None, debug_print=None
):
    """
    Copy and merge meshes by layer into a target collection.

    This is the core merge logic shared between file export and collection export.

    Args:
        asset_host: The asset host object (armature or mesh)
        target_collection: Collection to link copied objects to
        armature_copy: Optional copied armature (None for static/mesh-hosted assets)
        debug_print: Optional debug print function

    Returns:
        tuple: (merged_layer_objects, unrename_info)
            - merged_layer_objects: dict {layer_name: merged_mesh_object}
            - unrename_info: list of rename info for restoration
    """
    if debug_print is None:

        def debug_print(*args):
            pass

    asset_meshes_layers = get_asset_meshes_by_layer(asset_host)
    unrename_info = []
    merged_layer_objects = {}

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

            merge_onto_avatar_layer(layer_name, mesh_copy, armature_copy)
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

    return merged_layer_objects, unrename_info


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


def apply_armature_modifiers_and_remove(objects, armature, debug_print=None):
    """
    Apply armature modifiers to objects and remove the armature.

    Used for static exports where the armature should be baked into the mesh.

    Args:
        objects: Iterable of objects to process
        armature: The armature to apply and remove
        debug_print: Optional debug print function
    """
    if debug_print is None:

        def debug_print(*args):
            pass

    for obj in objects:
        if obj.type != "MESH":
            continue

        bpy.context.view_layer.objects.active = obj

        for mod in list(obj.modifiers):
            if mod.type == "ARMATURE" and mod.object == armature:
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                    debug_print(f"Applied armature modifier on {obj.name}")
                except RuntimeError as e:
                    debug_print(
                        f"⚠️ Could not apply armature modifier on {obj.name}: {e}"
                    )

    bpy.data.objects.remove(armature, do_unlink=True)
    debug_print("Removed armature for static export")
