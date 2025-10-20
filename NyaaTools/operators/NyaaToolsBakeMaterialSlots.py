import traceback
import os
import re
import time
import json
import numpy as np
import bpy
from bpy.props import StringProperty

from ..consts import PROP_AVATAR_EXPORT_PATH
from ..common.get_prop import get_prop
from ..common.renamer_restore import renamer_restore
from ..common.resolve_path import resolve_path
from ..image.material_analyzer import find_principled_bsdf
from ..image.texture_baker import bake_packed_texture


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
        
        # DEBUG: Extract UV data and original material image BEFORE baking and bail out early
        # debug_data = extract_uv_and_image_data(obj, mat, mat_name)
        # if save_debug_data(debug_data, export_dir, mat_name):
        #     debug_print(f"  🚀 Debug extraction complete - bailing out early")
        #     return  # Early exit for debugging
        
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
            packed_img = bake_packed_texture(mat, obj, format_string)
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
        debug_print(f"  🍞 Bake finished in {bake_duration} seconds")
        
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


def extract_uv_and_image_data(obj, material, material_name):
    """
    Extract UV triangle data and original material image pixels for debugging/testing purposes.
    This extracts UV data and finds the first connected image texture from the material.
    
    Args:
        obj: Blender object with UV data
        material: The material to extract image from
        material_name: Name of the material for file naming
        
    Returns:
        Dictionary with uv_faces and image_pixels data from original material
        
    Example output format (matching mock-texture.json):
    {
        "uv_faces": [
            [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8]]
        ],
        "image_pixels": [
            [1.0, 0.0, 0.0, 1.0],
            [0.0, 1.0, 0.0, 1.0],
            ...
        ],
        "image_dimensions": [256, 256]
    }
    """
    def debug_print(*msgs):
        print("      ", *msgs)
        return
    
    debug_print(f"🔍 Extracting UV data and original image for {material_name}")
    
    # Initialize result structure to match mock-texture.json format
    result = {
        "uv_faces": [],
        "image_pixels": [],
        "image_dimensions": []
    }
    
    # Extract UV triangle data
    if obj.data and obj.type == 'MESH' and obj.data.uv_layers:
        mesh = obj.data
        uv_layer = mesh.uv_layers[0]
        
        for face_idx, face in enumerate(mesh.polygons):
            # Collect UVs for this face
            uv_coords = []
            for loop_idx in face.loop_indices:
                uv_coord = uv_layer.data[loop_idx].uv
                uv_coords.append([float(uv_coord.x), float(uv_coord.y)])
            
            if len(uv_coords) >= 3:
                # Store UV coordinates as list of [u, v] pairs (matching mock format)
                result["uv_faces"].append(uv_coords)
        
        debug_print(f"  📐 Extracted {len(result['uv_faces'])} UV faces")
    else:
        debug_print(f"  ⚠️ No UV data found for object {obj.name}")
    
    # Find first connected image texture in the material
    if material and material.use_nodes and material.node_tree:
        image_texture_node = None
        
        # Search for Image Texture nodes
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                image_texture_node = node
                break
        
        if image_texture_node and image_texture_node.image:
            image = image_texture_node.image
            debug_print(f"  🖼️ Found connected image: {image.name}")
            
            # Extract image pixel data
            if image.pixels:
                W, H = image.size
                result["image_dimensions"] = [int(W), int(H)]
                
                # Convert pixels to flat list format (matching mock format)
                pixels = np.array(image.pixels, dtype=np.float32).reshape((H, W, -1))
                
                # Flatten to list of [r, g, b, a] arrays (matching mock format)
                result["image_pixels"] = pixels.reshape(-1, pixels.shape[2]).tolist()
                
                debug_print(f"  🖼️ Extracted {W}x{H} image with {pixels.shape[2]} channels")
            else:
                debug_print(f"  ⚠️ Image {image.name} has no pixel data")
        else:
            debug_print(f"  ⚠️ No connected image texture found in material")
    else:
        debug_print(f"  ⚠️ Material has no node tree or nodes")
    
    return result


def save_debug_data(debug_data, export_dir, material_name):
    """
    Save debug data to test-image.json file.
    
    Args:
        debug_data: Dictionary with uv_faces data
        export_dir: Export directory path
        material_name: Material name for file naming
    """
    def debug_print(*msgs):
        print("      ", *msgs)
        return
    
    # Sanitize material name for filename
    sanitized_name = sanitize_name(material_name)
    debug_file_path = os.path.join(export_dir, f"{sanitized_name}.test-image.json")
    
    try:
        with open(debug_file_path, 'w') as f:
            json.dump(debug_data, f, indent=2)
        debug_print(f"  💾 Saved debug data: {sanitized_name}.test-image.json")
        return True
    except Exception as e:
        debug_print(f"  ❌ Failed to save debug data: {e}")
        return False

