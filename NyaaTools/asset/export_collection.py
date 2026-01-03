"""
Collection export functionality.

Exports assets to a __Export__ collection and marks them as Blender assets
for use in downstream render scenes via the Asset Browser.
"""

import os

import bpy

from ..common.file_stuff import sanitize_name
from ..common.resolve_path import resolve_path
from ..common.renamer_restore import renamer_restore
from .merge_layers import (
    merge_asset_layers,
    copy_armature_to_collection,
    apply_armature_modifiers_and_remove,
)


EXPORT_COLLECTION_NAME = "__Export__"


def get_or_create_export_collection():
    """
    Get or create the __Export__ collection with proper configuration.

    Returns the collection, creating it if needed with:
    - Green color tag
    - Positioned at top of collection list
    - Hidden from viewport and render
    """
    collection = bpy.data.collections.get(EXPORT_COLLECTION_NAME)

    if collection is None:
        collection = bpy.data.collections.new(EXPORT_COLLECTION_NAME)
        bpy.context.scene.collection.children.link(collection)

    # Set color tag to green (COLOR_04)
    collection.color_tag = "COLOR_04"

    # Ensure it's in the scene collection
    if collection.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(collection)

    # Move to top of collection list by unlinking and relinking at index 0
    try:
        bpy.context.scene.collection.children.unlink(collection)
        # Link it back - Blender doesn't have direct index control,
        # but we can use move_above/move_below with operators if needed
        bpy.context.scene.collection.children.link(collection)
    except RuntimeError:
        pass

    return collection


def clear_export_collection():
    """Clear all objects from the __Export__ collection and purge orphans."""
    collection = bpy.data.collections.get(EXPORT_COLLECTION_NAME)
    if collection is None:
        return

    # Remove all objects from the collection
    for obj in list(collection.objects):
        # Unmark as Blender asset (removes fake user)
        if obj.asset_data:
            obj.asset_clear()
        # Clear any remaining fake users
        obj.use_fake_user = False
        # Now remove the object
        bpy.data.objects.remove(obj, do_unlink=True)

    # Purge orphaned data to prevent name collisions
    bpy.ops.outliner.orphans_purge(do_recursive=True)


def set_collection_visibility(collection, hide=True, hide_render=True):
    """
    Set viewport and render visibility for a collection.

    Args:
        collection: The collection to modify
        hide: If True, hide from viewport
        hide_render: If True, hide from renders (always True for __Export__)
    """
    # Hide in viewport at the collection level
    collection.hide_viewport = hide
    # Always hide __Export__ from renders
    collection.hide_render = hide_render

    # Also set view layer visibility if available
    view_layer = bpy.context.view_layer
    layer_collection = find_layer_collection(
        view_layer.layer_collection, collection.name
    )
    if layer_collection:
        layer_collection.exclude = False  # Don't exclude, keep in view layer
        layer_collection.hide_viewport = hide


def ensure_collection_accessible(collection):
    """
    Ensure a collection is accessible (not excluded, not hidden) for operations.

    Args:
        collection: The collection to make accessible
    """
    # Unhide at collection level
    collection.hide_viewport = False

    # Ensure it's in the view layer and not excluded
    view_layer = bpy.context.view_layer
    layer_collection = find_layer_collection(
        view_layer.layer_collection, collection.name
    )
    if layer_collection:
        layer_collection.exclude = False
        layer_collection.hide_viewport = False


def find_layer_collection(layer_collection, name):
    """Recursively find a LayerCollection by name."""
    if layer_collection.name == name:
        return layer_collection
    for child in layer_collection.children:
        result = find_layer_collection(child, name)
        if result:
            return result
    return None


def get_textures_directory(asset_host):
    """
    Get the textures directory path for an asset.

    Args:
        asset_host: The asset host object

    Returns:
        Path to textures directory or None
    """
    cfg = asset_host.nyaa_asset
    if len(cfg.export_profiles) > 0 and 0 <= cfg.active_export_index < len(
        cfg.export_profiles
    ):
        export_path = cfg.export_profiles[cfg.active_export_index].path
        if export_path:
            base_path = resolve_path(export_path, "temp")
            return os.path.join(os.path.dirname(base_path), "textures")

    # Fallback to blend file location
    blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd()
    return os.path.join(blend_dir, "textures")


def find_baked_textures(textures_dir, material_name):
    """
    Find baked texture files for a material.

    Args:
        textures_dir: Directory to search
        material_name: The material name

    Returns:
        dict: {dtp_format: filepath} for found textures
    """
    if not os.path.isdir(textures_dir):
        return {}

    found = {}
    mat_name = sanitize_name(material_name)

    for filename in os.listdir(textures_dir):
        # Expected format: {mat_name}.{dtp_format}.{ext}
        if not filename.startswith(mat_name + "."):
            continue

        parts = filename.rsplit(".", 2)
        if len(parts) >= 3:
            # parts[-1] is extension, parts[-2] is dtp_format
            dtp_format = parts[-2]
            filepath = os.path.join(textures_dir, filename)
            found[dtp_format] = filepath

    return found


def create_baked_material(original_mat, textures_dir):
    """
    Create a new material with baked textures connected to Principled BSDF.

    Args:
        original_mat: The original material
        textures_dir: Directory containing baked textures

    Returns:
        New material with baked textures, or None if no textures found
    """
    baked_textures = find_baked_textures(textures_dir, original_mat.name)
    if not baked_textures:
        return None

    # Create new material
    new_mat_name = f"{original_mat.name}_bake"
    new_mat = bpy.data.materials.new(name=new_mat_name)
    new_mat.use_nodes = True

    nodes = new_mat.node_tree.nodes
    links = new_mat.node_tree.links

    # Clear default nodes
    nodes.clear()

    # Create output and Principled BSDF
    output_node = nodes.new("ShaderNodeOutputMaterial")
    output_node.location = (300, 0)

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (0, 0)

    links.new(principled.outputs["BSDF"], output_node.inputs["Surface"])

    # Position tracking for texture nodes
    tex_x = -400
    tex_y = 300

    # Connect textures based on DTP format
    for dtp_format, filepath in baked_textures.items():
        # Create image texture node
        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.location = (tex_x, tex_y)
        tex_y -= 300

        # Load image
        img = bpy.data.images.load(filepath, check_existing=True)
        tex_node.image = img

        # Connect based on format
        if dtp_format in ("rgba", "rgb"):
            tex_node.image.colorspace_settings.name = "sRGB"
            links.new(tex_node.outputs["Color"], principled.inputs["Base Color"])
            if dtp_format == "rgba":
                links.new(tex_node.outputs["Alpha"], principled.inputs["Alpha"])
                new_mat.blend_method = "HASHED"

        elif dtp_format == "normalgl":
            tex_node.image.colorspace_settings.name = "Non-Color"
            normal_map = nodes.new("ShaderNodeNormalMap")
            normal_map.location = (tex_x + 200, tex_y + 300)
            links.new(tex_node.outputs["Color"], normal_map.inputs["Color"])
            links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])

        elif dtp_format == "emission":
            tex_node.image.colorspace_settings.name = "sRGB"
            links.new(tex_node.outputs["Color"], principled.inputs["Emission Color"])
            principled.inputs["Emission Strength"].default_value = 1.0

        elif "-" in dtp_format:
            # Packed channels like me-ro-sp, me-sm-1, etc.
            tex_node.image.colorspace_settings.name = "Non-Color"

            channels = dtp_format.split("-")
            separate_node = nodes.new("ShaderNodeSeparateColor")
            separate_node.location = (tex_x + 200, tex_y + 300)
            links.new(tex_node.outputs["Color"], separate_node.inputs["Color"])

            channel_outputs = ["Red", "Green", "Blue"]
            channel_map = {
                "me": "Metallic",
                "ro": "Roughness",
                "sp": "Specular IOR Level",
                "sm": None,  # Smoothness needs inversion
                "ao": None,  # AO not directly connected in Principled
            }

            for i, ch in enumerate(channels[:3]):
                if ch in channel_map and channel_map[ch]:
                    links.new(
                        separate_node.outputs[channel_outputs[i]],
                        principled.inputs[channel_map[ch]],
                    )
                elif ch == "sm":
                    # Smoothness = 1 - Roughness, need invert node
                    invert = nodes.new("ShaderNodeMath")
                    invert.operation = "SUBTRACT"
                    invert.inputs[0].default_value = 1.0
                    invert.location = (tex_x + 400, tex_y + 300 - i * 50)
                    links.new(
                        separate_node.outputs[channel_outputs[i]], invert.inputs[1]
                    )
                    links.new(invert.outputs["Value"], principled.inputs["Roughness"])

    return new_mat


TEMP_SCENE_NAME = "Temp Merge & Export"


def export_to_collection(
    asset_host, export_static=False, bake_after_export=False, debug_print=None
):
    """
    Export asset to __Export__ collection and mark as Blender asset.

    Uses the same layer merge logic as file-based export to ensure consistency.
    Creates a temp scene for merging (required by merge operators), then moves
    the result to the __Export__ collection.

    Args:
        asset_host: The asset host object (armature or mesh) with nyaa_asset config
        export_static: If True, apply pose and modifiers, remove armature
        bake_after_export: If True, bake textures from merged meshes before moving to collection
        debug_print: Optional function for debug output

    Returns:
        List of exported objects
    """
    if debug_print is None:

        def debug_print(*args):
            print("   ", *args)

    cfg = asset_host.nyaa_asset
    asset_name = cfg.asset_name
    is_static_asset = asset_host.type == "MESH"
    treat_as_static = is_static_asset or export_static

    # Purge orphans first to avoid name collisions with deleted objects
    bpy.ops.outliner.orphans_purge(do_recursive=True)

    # Get or create export collection and clear it
    export_collection = get_or_create_export_collection()
    clear_export_collection()

    # Ensure collection is accessible for operations
    ensure_collection_accessible(export_collection)

    # Get textures directory for material assignment
    textures_dir = get_textures_directory(asset_host)

    # Create temp scene for merge operations (required by merge_onto_avatar_layer)
    temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
    if temp_scene:
        bpy.data.scenes.remove(temp_scene, do_unlink=True)
        bpy.ops.outliner.orphans_purge(do_recursive=True)

    temp_scene = bpy.data.scenes.new(name=TEMP_SCENE_NAME)
    original_scene = bpy.context.window.scene
    bpy.context.window.scene = temp_scene

    # Update view layer after scene switch
    bpy.context.view_layer.update()

    exported_objects = []
    unrename_info = []
    error = None

    try:
        armature_copy = None

        # For armature-based assets, copy armature (unless exporting static)
        if not is_static_asset and not export_static:
            armature_copy, arm_unrename = copy_armature_to_collection(
                asset_host, temp_scene.collection, asset_name, debug_print
            )
            unrename_info.extend(arm_unrename)

        # Merge meshes by layer in temp scene
        merged_layers, mesh_unrename = merge_asset_layers(
            asset_host, temp_scene.collection, armature_copy, debug_print
        )
        unrename_info.extend(mesh_unrename)

        # Apply armature modifier and remove armature if exporting static
        if export_static and armature_copy:
            apply_armature_modifiers_and_remove(
                temp_scene.objects, armature_copy, debug_print
            )
            armature_copy = None

        # Move objects from temp scene to export collection
        for obj in list(temp_scene.collection.objects):
            # Unlink from temp scene
            temp_scene.collection.objects.unlink(obj)
            # Link to export collection
            export_collection.objects.link(obj)
            exported_objects.append(obj)

        # Mark as Blender asset
        if armature_copy and not treat_as_static:
            # For rigged assets, mark the armature
            armature_copy.asset_mark()
            armature_copy.asset_generate_preview()
            debug_print(f"✅ Marked as asset: {armature_copy.name}")
        else:
            # For static exports, mark each mesh
            for obj in exported_objects:
                if obj.type == "MESH":
                    obj.asset_mark()
                    obj.asset_generate_preview()
                    debug_print(f"✅ Marked as asset: {obj.name}")

    except Exception as e:
        error = e

    finally:
        # Restore original scene and clean up temp scene
        bpy.context.window.scene = original_scene

        temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
        if temp_scene:
            bpy.data.scenes.remove(temp_scene, do_unlink=True)
            bpy.ops.outliner.orphans_purge(do_recursive=True)

        # Restore any objects that were renamed due to conflicts
        renamer_restore(unrename_info)

        # Force context update to ensure selection is recognized
        bpy.context.view_layer.update()

        if error:
            raise error

    # Set up pending bake context if baking is requested
    # For collection export, meshes are now in the main scene (export collection)
    baking_pending = False
    if bake_after_export and exported_objects:
        from ..panels.operators_bake import set_pending_bake_context

        mesh_objects = [obj for obj in exported_objects if obj.type == "MESH"]
        if mesh_objects:
            # Capture values for cleanup lambda
            collection_name = export_collection.name
            mesh_names = [obj.name for obj in mesh_objects]
            tex_dir = textures_dir

            def cleanup_collection_export():
                """Assign baked materials and hide collection after baking."""
                # Assign baked materials to exported meshes
                for mesh_name in mesh_names:
                    obj = bpy.data.objects.get(mesh_name)
                    if obj and obj.type == "MESH":
                        for slot in obj.material_slots:
                            if slot.material:
                                baked_mat = create_baked_material(
                                    slot.material, tex_dir
                                )
                                if baked_mat:
                                    slot.material = baked_mat
                                    print(
                                        f"🎨 Assigned baked material: {baked_mat.name}"
                                    )

                # Hide export collection
                coll = bpy.data.collections.get(collection_name)
                if coll:
                    set_collection_visibility(coll, hide=True, hide_render=True)

            set_pending_bake_context(
                mesh_objects,
                cfg.bake_images,
                textures_dir,
                on_cleanup=cleanup_collection_export,
            )
            baking_pending = True
            debug_print(f"🍞 Baking queued for {len(mesh_objects)} exported meshes")
    else:
        # Only hide collection if not baking (baking will hide it when done)
        set_collection_visibility(export_collection, hide=True, hide_render=True)

    return exported_objects, baking_pending
