import traceback
import os
import re
import bpy
from bpy.props import StringProperty

from ..consts import PROP_AVATAR_EXPORT_PATH
from ..common.get_prop import get_prop
from ..common.renamer_restore import renamer_restore
from ..common.resolve_path import resolve_path
from ..image.material_analyzer import find_principled_bsdf, has_socket_input, find_largest_texture_resolution
from ..image.texture_baker import bake_socket
from ..image.texture_utils import pack_rgba, pack_pbr


TEMP_SCENE_NAME = "Temp Bake Material Slots"


class NyaaToolsBakeMaterialSlots(bpy.types.Operator):
    """Bake all material slots on the selected object to texture files"""

    bl_idname = "nyaa.bake_material_slots"
    bl_label = "Bake Material Slots"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            # Validate file is saved
            if not bpy.data.filepath:
                self.report({"ERROR"}, "File must be saved before baking.")
                return {"CANCELLED"}
            
            # Validate an object is selected
            if not context.active_object:
                self.report({"ERROR"}, "No object selected.")
                return {"CANCELLED"}
            
            selected_obj = context.active_object
            
            # Validate object has materials
            if not selected_obj.data.materials:
                self.report({"ERROR"}, "Object has no materials.")
                return {"CANCELLED"}
            
            # Validate material names are not default
            default_material_pattern = re.compile(r'^(Material)?\.*[0-9]{3}$')
            for mat in selected_obj.data.materials:
                if mat and default_material_pattern.match(mat.name):
                    self.report({"ERROR"}, f"Don't forget to give material slot a good name: '{mat.name}'")
                    return {"CANCELLED"}
            
            perform_bake(selected_obj)
            
            self.report({"INFO"}, "Baking completed successfully!")
            return {"FINISHED"}
            
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_bake(obj):
    def debug_print(*msgs):
        print("   ", *msgs)
        return
    
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    
    # Create a temporary scene for operations
    temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
    if temp_scene:
        bpy.data.scenes.remove(temp_scene, do_unlink=True)
        temp_scene = None
        bpy.ops.outliner.orphans_purge(do_recursive=True)
    
    temp_scene = bpy.data.scenes.new(name=TEMP_SCENE_NAME)
    original_scene = bpy.context.window.scene
    bpy.context.window.scene = temp_scene
    
    # Objects that already exist with some desired name are temporarily renamed. Restore them in the end.
    unrename_info = []
    
    error = None
    try:
        bpy.ops.wm.console_toggle()
        
        # Copy object to temp scene
        debug_print(f"Copying object {obj.name} to temp scene...")
        
        # Create a copy of the object
        obj_copy = obj.copy()
        obj_copy.data = obj.data.copy()
        temp_scene.collection.objects.link(obj_copy)
        
        # Determine output directory
        export_dir = get_export_directory(obj)
        debug_print(f"Export directory: {export_dir}")
        
        # Bake all material slots
        bake_material_slots(obj_copy, export_dir, unrename_info)
        
    except Exception as e:
        error = e
    
    finally:
        # Cleanup - let the error pass through
        temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
        if temp_scene:
            bpy.context.window.scene = original_scene
            
            # Delete temp scene
            bpy.data.scenes.remove(temp_scene, do_unlink=True)
            bpy.ops.outliner.orphans_purge(do_recursive=True)
            
            # Restore original names
            renamer_restore(unrename_info)
        
        bpy.ops.wm.console_toggle()
        
        if error:
            raise error


def get_export_directory(obj):
    """Determine the export directory for textures."""
    
    # Try to get avatar export path from parent armature
    armature = None
    if obj.parent and obj.parent.type == 'ARMATURE':
        armature = obj.parent
    
    if armature:
        export_path = get_prop(armature, PROP_AVATAR_EXPORT_PATH)
        if export_path:
            # Use avatar export path
            base_path = resolve_path(export_path)
            return os.path.join(os.path.dirname(base_path), "textures")
    
    # Otherwise use blend file location
    blend_dir = os.path.dirname(bpy.data.filepath)
    return os.path.join(blend_dir, "textures")


def bake_material_slots(obj, export_dir, unrename_info):
    def debug_print(*msgs):
        print("   ", *msgs)
        return
    
    # Ensure export directory exists
    os.makedirs(export_dir, exist_ok=True)
    
    # Iterate through material slots
    for slot_idx, slot in enumerate(obj.material_slots):
        mat = slot.material
        if not mat:
            debug_print(f"Slot {slot_idx}: No material, skipping")
            continue
        
        debug_print(f"")
        debug_print(f"Processing material: {mat.name}")
        
        # Find Principled BSDF
        principled = find_principled_bsdf(mat)
        if not principled:
            debug_print(f"  No Principled BSDF found, skipping")
            continue
        
        # Sanitize material name for file output
        mat_name = sanitize_name(mat.name)
        
        # Dictionary to hold baked images in memory
        baked_images = {}
        
        # Define socket groups for resolution detection
        socket_groups = {
            'diffuse': [
                ('Base Color', 'base_color', False),
                ('Alpha', 'alpha', False)
            ],
            'pbr': [
                ('Metallic', 'metallic', False),
                ('Specular IOR Level', 'specular', False),
                ('Roughness', 'roughness', False)
            ],
            'normal': [
                ('Normal', 'normal', True)
            ],
            'emission': [
                ('Emission Color', 'emission', False)
            ]
        }
        
        # Determine resolution per pack
        debug_print(f"  Sockets:")
        pack_resolutions = {}
        
        for pack_name, sockets in socket_groups.items():
            max_resolution = None
            any_has_input = False
            
            for socket_name, key, is_normal in sockets:
                socket = principled.inputs.get(socket_name)
                if not socket:
                    continue
                
                if has_socket_input(socket):
                    any_has_input = True
                    res = find_largest_texture_resolution(socket, mat)
                    if res:
                        if max_resolution is None or (res[0] * res[1] > max_resolution[0] * max_resolution[1]):
                            max_resolution = res
            
            if any_has_input:
                if max_resolution:
                    pack_resolutions[pack_name] = max_resolution
                    debug_print(f"      {pack_name}: {max_resolution[0]}x{max_resolution[1]} (detected)")
                else:
                    pack_resolutions[pack_name] = (512, 512)
                    debug_print(f"      {pack_name}: 512x512 (default - has input but no textures)")
            else:
                pack_resolutions[pack_name] = (8, 8)
                debug_print(f"      {pack_name}: 8x8 (all defaults)")
        
        # Bake all sockets using pack resolution
        for pack_name, sockets in socket_groups.items():
            resolution = pack_resolutions[pack_name]
            
            for socket_name, key, is_normal in sockets:
                socket = principled.inputs.get(socket_name)
                if not socket:
                    continue
                
                debug_print(f"  🔧 Baking {socket_name}: {resolution[0]}x{resolution[1]} (from {pack_name} pack)")
                
                # Determine default value for this socket type
                default_val = None
                if is_normal:
                    # Normal maps default to flat normal (0.5, 0.5, 1.0)
                    default_val = (0.5, 0.5, 1.0)
                elif not has_socket_input(socket) and hasattr(socket, 'default_value'):
                    value = socket.default_value
                    if isinstance(value, (tuple, list)) and len(value) >= 3:
                        debug_print(f"    Value: RGB({value[0]:.3f}, {value[1]:.3f}, {value[2]:.3f})")
                    else:
                        debug_print(f"    Value: {value}")
                
                # Bake to memory
                baked_img = bake_socket(
                    mat,
                    obj,
                    socket_name,
                    resolution,
                    is_normal,
                    default_val
                )
                
                if baked_img:
                    baked_images[key] = baked_img
                    debug_print(f"  🍞 Baked successfully")
                else:
                    debug_print(f"  ❌ Baking failed")
        
        # Pack and save final textures
        debug_print(f"  📦 Packing channels:")
        
        # 1. Diffuse: RGB (Base Color) + Alpha (always PNG)
        diffuse_img = pack_rgba(
            baked_images.get('base_color'),
            baked_images.get('alpha'),
            default_rgb=(1.0, 1.0, 1.0),
            default_alpha=1.0
        )
        diffuse_path = os.path.join(export_dir, f"{mat_name}.baked.rgba.png")
        if save_image(diffuse_img, diffuse_path):
            debug_print(f"    💾 Saved: {mat_name}.baked.rgba.png")
        
        # 2. PBR: Metallic + Specular IOR Level + Roughness (user-specified format)
        pbr_img = pack_pbr(
            baked_images.get('metallic'),
            baked_images.get('specular'),
            baked_images.get('roughness'),
            default_metallic=0.0,
            default_specular=0.5,
            default_roughness=0.5
        )
        pbr_path = os.path.join(export_dir, f"{mat_name}.baked.me-sp-ro.png")
        if save_image(pbr_img, pbr_path):
            debug_print(f"    💾 Saved: {mat_name}.baked.me-sp-ro.png")
        
        # 3. Normal
        if 'normal' in baked_images:
            normal_img = baked_images['normal']
            normal_path = os.path.join(export_dir, f"{mat_name}.baked.normalgl.png")
            if save_image(normal_img, normal_path):
                debug_print(f"    💾 Saved: {mat_name}.baked.normalgl.png")
        
        # 4. Emission
        if 'emission' in baked_images:
            emission_img = baked_images['emission']
            emission_path = os.path.join(export_dir, f"{mat_name}.baked.emission.png")
            if save_image(emission_img, emission_path):
                debug_print(f"    💾 Saved: {mat_name}.baked.emission.png")
        
        debug_print(f"  ✅ Material {mat.name} completed")


def save_image(image, output_path):
    """
    Save a Blender image to PNG file and clean up from memory.
    
    Args:
        image: The Blender image to save
        output_path: Path to save the PNG file
    
    Returns:
        True if successful, False otherwise
    """
    if not image:
        return False
    
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save as PNG
        image.filepath_raw = output_path
        image.file_format = 'PNG'
        image.save()
        
        # Clean up the image from Blender's memory
        bpy.data.images.remove(image)
        
        return True
    except Exception as e:
        print(f"Failed to save image to {output_path}: {e}")
        if image and image.name in bpy.data.images:
            bpy.data.images.remove(image)
        return False


def sanitize_name(name):
    """Sanitize filename to be Windows-safe, replacing forbidden characters with underscore."""
    # Windows forbidden characters: < > : " / \ | ? *
    return re.sub(r'[<>:"/\\|?*]', '_', name)

