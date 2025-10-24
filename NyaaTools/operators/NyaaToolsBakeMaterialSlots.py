import traceback
import os
import re
import time
import bpy

from ..consts import PROP_AVATAR_EXPORT_PATH
from ..common.get_prop import get_prop
from ..common.renamer_restore import renamer_restore
from ..common.resolve_path import resolve_path
from ..image.material_analyzer import find_principled_bsdf
from ..image.texture_baker import bake_dtp_texture


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
    
    # Separate mesh by materials using built-in operator
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    
    # Enter edit mode, select all, and separate by material
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='MATERIAL')
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Get all remaining mesh objects (these are our separated single-material objects)
    bake_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    
    # Helper functions to manage object visibility and materials
    def disable_render(obj):
        """Disable rendering for a single object"""
        obj.hide_viewport = True
        obj.hide_render = True
        
        # Clear materials to prevent node conflicts
        for slot in obj.material_slots:
            slot.material = None
    
    def enable_render(obj, original_material):
        """Restore a single object to its original state"""
        # Restore material (only one slot since we separated by material)
        if len(obj.material_slots) > 0:
            obj.material_slots[0].material = original_material
        
        # Restore visibility
        obj.hide_viewport = False
        obj.hide_render = False

    object_states = {}  # Track original material per object name
    for obj in bake_objects:
        # Store original material (only one since we separated by material)
        object_states[obj.name] = obj.material_slots[0].material if len(obj.material_slots) > 0 else None
        # Disable render
        disable_render(obj)
    
    # Process each separated mesh object (each has exactly one material)
    for bake_obj in bake_objects:
        # Get material from stored state
        mat = object_states[bake_obj.name]
        if not mat:
            debug_print(f"Object {bake_obj.name}: No material, skipping")
            continue
            
        mat_name = mat.name
        
        # Show only this object for baking and restore its material
        if bake_obj.name in object_states:
            original_material = object_states[bake_obj.name]
            enable_render(bake_obj, original_material)

        debug_print(f"")
        debug_print(f"📦 Material: {mat_name}")

        # Find Principled BSDF
        principled = find_principled_bsdf(mat)
        if not principled:
            debug_print("❌ No Principled BSDF found")
            # Hide this object after baking and clear its material again
            disable_render(bake_obj)
            raise Exception("No Principled BSDF found")
        
        # Sanitize material name for file output
        mat_name = sanitize_name(mat.name)
        
        # Define pack configurations with format strings
        pack_configs = [
            ('rgba', 'baked.rgba.png'),
            ('me-sp-ro', 'baked.me-sp-ro.png'),
            ('normalgl', 'baked.normalgl.png'),
            ('emission', 'baked.emission.png'),
        ]
        
        # Bake and save packed textures
        bake_start_time = time.time()
        for format_string, filename in pack_configs:
            packed_img = bake_dtp_texture(format_string, bake_obj, mat)
            if packed_img:
                save_path = os.path.join(export_dir, f"{mat_name}.{filename}")
                if save_image(packed_img, save_path):
                    debug_print(f"    💾 Saved: {mat_name}.{filename}")
                else:
                    debug_print(f"    ❌ Failed to save: {mat_name}.{filename}")
            else:
                debug_print(f"    ❌ Baking failed for {format_string}")
        
        bake_end_time = time.time()
        bake_duration = int(bake_end_time - bake_start_time)
        debug_print(f"🍞 Bake finished in {bake_duration} seconds")
        
        # Hide this object after baking and clear its material again
        disable_render(bake_obj)
        
        debug_print(f"✅ Material {mat_name} completed")


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
