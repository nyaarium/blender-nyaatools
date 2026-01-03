"""
VotV (Voices of the Void) export functionality.

Handles the specialized export process for VotV including:
- Icon rendering
- Mesh merging and triangulation
- UCX collision objects
- Material baking
- properties.cfg generation
"""

import os
import time
import bpy

from ..common.file_stuff import sanitize_name
from ..common.renamer_rename import rename_object, rename_material
from ..common.resolve_path import resolve_path
from ..image.material_analyzer import find_principled_bsdf
from ..image.texture_baker import bake_dtp_texture
from ..image.texture_utils import save_image_as_png

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

    # Only 1 mesh allowed - merge everything
    bpy.ops.object.select_all(action="DESELECT")

    target_obj = None
    first_obj = None
    for obj in temp_scene.objects:
        if obj.type == "MESH":
            if obj.name == clean_asset_name:
                target_obj = obj
                break
            elif first_obj is None:
                first_obj = obj

    if target_obj is None:
        target_obj = first_obj

    if target_obj.name != clean_asset_name:
        unrename_info.extend(rename_object(target_obj, clean_asset_name))

    # Merge all meshes
    for obj in temp_scene.objects:
        if obj.type == "MESH":
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

    # Copy UCX collision objects
    ucx_objects = [obj for obj in bpy.data.objects if obj.name.startswith("UCX_")]
    if ucx_objects:
        for ucx_object in ucx_objects:
            ucx_object_copy = ucx_object.copy()
            ucx_object_copy.data = ucx_object.data.copy()
            temp_scene.collection.objects.link(ucx_object_copy)

            bpy.context.view_layer.objects.active = ucx_object_copy
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

    # Bake materials
    _bake_votv_materials(target_obj, temp_scene, export_dir, debug_print)

    # Write properties.cfg
    _write_properties_cfg(export_dir, debug_print)


def _bake_votv_materials(target_obj, temp_scene, export_dir, debug_print):
    """Bake materials for VotV export."""

    # Remove UCX objects
    ucx_objects = [obj for obj in temp_scene.objects if obj.name.startswith("UCX_")]
    for ucx_object in ucx_objects:
        bpy.data.objects.remove(ucx_object)

    # Separate by material
    bpy.ops.object.select_all(action="DESELECT")
    target_obj.select_set(True)
    bpy.context.view_layer.objects.active = target_obj

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="MATERIAL")
    bpy.ops.object.mode_set(mode="OBJECT")

    bake_objects = [obj for obj in temp_scene.objects if obj.type == "MESH"]

    debug_print("\n")

    def disable_render(obj):
        obj.hide_viewport = True
        obj.hide_render = True
        for slot in obj.material_slots:
            slot.material = None

    def enable_render(obj, original_material):
        if len(obj.material_slots) > 0:
            obj.material_slots[0].material = original_material
        obj.hide_viewport = False
        obj.hide_render = False

    object_states = {}
    for obj in bake_objects:
        object_states[obj.name] = (
            obj.material_slots[0].material if len(obj.material_slots) > 0 else None
        )
        disable_render(obj)

    for bake_obj in bake_objects:
        mat = object_states[bake_obj.name]
        mat_name = mat.name

        if bake_obj.name in object_states:
            original_material = object_states[bake_obj.name]
            enable_render(bake_obj, original_material)

        debug_print("\n")
        debug_print(f"📦 Material: {mat_name}")

        principled_result = find_principled_bsdf(mat)

        if not principled_result:
            debug_print("❌ No Principled BSDF found")
            raise Exception("No Principled BSDF found")

        principled_bsdf = principled_result["principled_bsdf"]
        debug_print(f"🔍 Found Principled BSDF: {principled_bsdf.name}")

        pack_configs = [
            ("rgba", "diffuse_{mat_name}.png"),
            ("me-sp-ro", "pbr_{mat_name}.png"),
            ("normalgl", "normal_{mat_name}.png"),
            ("emission", "emissive_{mat_name}.png"),
        ]

        bake_start_time = time.time()
        for format_string, filename_template in pack_configs:
            if format_string == "rgba":
                max_resolution = (2048, 2048)
            else:
                max_resolution = (1024, 1024)

            packed_img = bake_dtp_texture(
                format_string, bake_obj, mat, max_resolution=max_resolution
            )
            if packed_img:
                filename = filename_template.format(mat_name=mat_name)
                save_path = os.path.join(export_dir, filename)
                if save_image_as_png(packed_img, save_path):
                    debug_print(f"    💾 Saved: {filename}")
                else:
                    debug_print(f"    ❌ Failed to save: {filename}")
            else:
                debug_print(f"    ❌ Baking failed for {format_string}")

        bake_end_time = time.time()
        bake_duration = int(bake_end_time - bake_start_time)
        debug_print(f"🍞 Bake finished in {bake_duration} seconds")

        disable_render(bake_obj)

        debug_print(f"✅ Material {mat_name} completed")

    debug_print("\n")
    debug_print("Material Baking Complete")
    debug_print("\n")


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
