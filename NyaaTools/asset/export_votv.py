"""
VotV (Voices of the Void) export functionality.

Handles the specialized export process for VotV including:
- Icon rendering
- Mesh merging and triangulation
- UCX collision objects
- properties.cfg generation

Note: Material baking is handled by the bake queue system, not this module.
"""

import os
import bpy

from ..common.file_stuff import sanitize_name
from ..common.renamer_rename import rename_object, rename_material
from ..common.resolve_path import resolve_path

from .asset_lookup import get_export_path_from_asset


def render_votv_icon(asset_host, asset_name, debug_print):
    """
    Render the camera icon for VotV export.

    Args:
        asset_host: The asset host object
        asset_name: Clean asset name for folder
        debug_print: Debug print function
    """
    export_path = get_export_path_from_asset(asset_host)
    if not export_path:
        return

    # Find first camera in the scene
    camera = None
    for obj in bpy.context.scene.objects:
        if obj.type == "CAMERA":
            camera = obj
            break

    if not camera:
        return

    # Store original render settings
    original_scene = bpy.context.scene
    original_resolution_x = original_scene.render.resolution_x
    original_resolution_y = original_scene.render.resolution_y
    original_file_format = original_scene.render.image_settings.file_format
    original_color_mode = original_scene.render.image_settings.color_mode
    original_color_depth = original_scene.render.image_settings.color_depth

    # Check if resolution is square and warn if not
    if original_resolution_x != original_resolution_y:
        debug_print(
            f"⚠️ Render resolution is not square ({original_resolution_x}x{original_resolution_y}). Resolution will be adjusted to 128x128."
        )

    # Hide UCX_ collision objects from rendering
    ucx_objects = [
        obj for obj in bpy.context.scene.objects if obj.name.lower().startswith("ucx_")
    ]
    for ucx_obj in ucx_objects:
        ucx_obj.hide_render = True

    # Set camera as active and render
    bpy.context.view_layer.objects.active = camera
    bpy.context.scene.camera = camera

    # Temporarily set render resolution to 128x128
    original_scene.render.resolution_x = 128
    original_scene.render.resolution_y = 128

    # Set render format to 8-bit PNG for maximum compatibility
    original_scene.render.image_settings.file_format = "PNG"
    original_scene.render.image_settings.color_mode = "RGB"
    original_scene.render.image_settings.color_depth = "8"

    # Render the current frame
    bpy.ops.render.render()

    # Save the rendered image as icon.png
    render_result = bpy.data.images["Render Result"]
    if render_result:
        clean_asset_name = sanitize_name(asset_name, strict=True)
        if export_path.endswith(clean_asset_name):
            asset_export_dir = export_path
        else:
            asset_export_dir = os.path.join(export_path, clean_asset_name)

        os.makedirs(asset_export_dir, exist_ok=True)

        icon_path = os.path.join(asset_export_dir, "icon.png")
        render_result.save_render(icon_path)
        debug_print(f"Saved camera icon: {icon_path}")

    # Restore original render settings
    original_scene.render.resolution_x = original_resolution_x
    original_scene.render.resolution_y = original_resolution_y
    original_scene.render.image_settings.file_format = original_file_format
    original_scene.render.image_settings.color_mode = original_color_mode
    original_scene.render.image_settings.color_depth = original_color_depth


def export_votv(asset_name, temp_scene, export_path, unrename_info, debug_print):
    """
    Export asset in VotV format.

    Args:
        asset_name: The asset name
        temp_scene: The temporary scene with processed objects
        export_path: Base export path
        unrename_info: List to track renamed objects for restoration
        debug_print: Debug print function
    """
    clean_asset_name = sanitize_name(asset_name, strict=True)

    # Check if export path already ends with asset name
    if export_path.endswith(clean_asset_name):
        asset_export_dir = export_path
    else:
        asset_export_dir = os.path.join(export_path, clean_asset_name)

    path = resolve_path(asset_export_dir, clean_asset_name + ".obj")

    export_dir = os.path.dirname(path)
    os.makedirs(export_dir, exist_ok=True)

    # Only 1 mesh allowed - merge everything (exclude UCX collision objects)
    bpy.ops.object.select_all(action="DESELECT")

    target_obj = None
    first_obj = None
    for obj in temp_scene.objects:
        if obj.type == "MESH" and not obj.name.startswith("UCX_"):
            if obj.name == clean_asset_name:
                target_obj = obj
                break
            elif first_obj is None:
                first_obj = obj

    if target_obj is None:
        target_obj = first_obj

    if target_obj.name != clean_asset_name:
        unrename_info.extend(rename_object(target_obj, clean_asset_name))

    # Merge all meshes (exclude UCX collision objects - they're handled separately)
    meshes_to_join = [
        obj
        for obj in temp_scene.objects
        if obj.type == "MESH" and not obj.name.startswith("UCX_")
    ]

    for obj in meshes_to_join:
        obj.select_set(True)

    bpy.context.view_layer.objects.active = target_obj
    bpy.ops.object.join()
    bpy.ops.object.select_all(action="DESELECT")

    # Sanitize material names
    for mat in target_obj.data.materials:
        sanitized_name = sanitize_name(mat.name, strict=True)
        unrename_info.extend(rename_material(mat, sanitized_name))

    # Triangulate
    bpy.context.view_layer.objects.active = target_obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.object.mode_set(mode="OBJECT")

    # UCX collision objects should already be in temp_scene from merge_asset_layers
    # Just ensure they're triangulated
    ucx_objects = [obj for obj in temp_scene.objects if obj.name.startswith("UCX_")]
    if ucx_objects:
        for ucx_object in ucx_objects:
            bpy.context.view_layer.objects.active = ucx_object
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.quads_convert_to_tris()
            bpy.ops.object.mode_set(mode="OBJECT")
    else:
        raise Exception(
            "Missing collision objects. Make sure there are objects named UCX_*"
        )

    # Export OBJ
    bpy.ops.wm.obj_export(
        filepath=path,
        check_existing=False,
        filter_glob="*.obj",
        global_scale=100.0,
    )

    # Write properties.cfg
    _write_properties_cfg(export_dir, debug_print)


def _write_properties_cfg(export_dir, debug_print):
    """Write the properties.cfg file for VotV."""

    properties_cfg_path = os.path.join(export_dir, "properties.cfg")
    if not os.path.exists(properties_cfg_path):
        properties_content = """##########################
# Main material settings

# Physical material type
#  0 - default
#  1 - wood
#  2 - metal
#  3 - concrete
#  4 - rubber
#  5 - paper
#  6 - hollow metal
#  7 - flesh
#  8 - plush
#  9 - metal2
# 10 - pinecone
# 11 - glass
# 12 - cardboard
# 13 - heavy metal
# 14 - no sound
# 15 - rubber2
physical_material=0

# Emissive strength
emissive_strength=1

##########################
# Light source settings

# is_lamp=1
# lamp_color=(R=1,G=1,B=1)
# lamp_offset=(X=0,Y=0,Z=0)
# lamp_intensity=5000
# lamp_attenuation=2500
# lamp_shadows=0

##########################
# Per-material filters

# filter_diffuse_mat1=0
# filter_pbr_mat1=0
# filter_normal_mat1=0
# filter_emissive_mat1=0
# 
# filter_diffuse_mat2=0
# filter_pbr_mat2=0
# filter_normal_mat2=0
# filter_emissive_mat2=0
# 
# filter_diffuse_mat3=0
# filter_pbr_mat3=0
# filter_normal_mat3=0
# filter_emissive_mat3=0
# 
# ...
"""
        with open(properties_cfg_path, "w", newline="\n") as f:
            f.write(properties_content)
        debug_print(f"✅ Created: properties.cfg")
