import traceback
import os
import re
import bpy
from bpy.props import StringProperty

from ..mesh.cleanup_mesh import cleanup_mesh
from ..consts import EXPORT_COLLECTION, PROP_AVATAR_EXPORT_PATH
from ..common.deselect_all import deselect_all
from ..common.get_prop import get_prop
from ..common.renamer_rename import rename_object, rename_material
from ..common.renamer_restore import renamer_restore
from ..common.resolve_path import resolve_path
from ..common.select_collection import select_collection
from ..common.selection_add import selection_add
from ..avatar.find_scene_avatars import find_scene_avatars
from ..avatar.get_avatar_armature import get_avatar_armature
from ..avatar.get_avatar_layers import get_avatar_layers
from ..avatar.get_avatar_meshes import get_avatar_meshes
from ..avatar.merge_onto_avatar_layer import merge_onto_avatar_layer
from ..image.material_analyzer import find_principled_bsdf, has_socket_input, find_largest_texture_resolution
from ..image.texture_baker import bake_socket
from ..image.texture_utils import pack_rgba, pack_pbr, save_image_as_png


TEMP_SCENE_NAME = "Temp Merge & Export"


class NyaaToolsAvatarMergeExport(bpy.types.Operator):
    """Merge and export tool. For Voices of the Void, configure the path to the printer directory: "...\\VotV\\Assets\\meshes\\printer\\\""""

    bl_idname = "nyaa.avatar_merge_export"
    bl_label = "Merge & Export"
    bl_options = {"REGISTER", "UNDO"}

    avatar_name: StringProperty(name="Avatar Name", default="")

    export_format: StringProperty(name="Export Format", default="fbx")

    def execute(self, context):
        try:
            if not self.avatar_name:
                self.report({"ERROR"}, "Specify an avatar name.")
                return {"CANCELLED"}

            perform_merge_export(
                self.avatar_name,
                self.export_format
            )

            armature = get_avatar_armature(self.avatar_name)
            path = get_prop(armature, PROP_AVATAR_EXPORT_PATH)
            if path:
                path = resolve_path(path, self.avatar_name)

            self.report({"INFO"}, "Export successful!  " + path)

            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


# Returns a list of avatar layers as pairs: [path_avatar_name, path_layer_name]
# If avatar_name is given, only returns layers for that avatar (as pairs above)
# def get_avatar_layers(mesh_object, avatar_name)

# Returns a list of mesh names that are part of that avatar
# get_avatar_meshes(avatar_name)


def perform_merge_export(avatar_name, export_format):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.outliner.orphans_purge(do_recursive=True)
    
    # Get all layers on the avatar in this scene
    avatar_meshes_layers = find_scene_avatars(avatar_name)

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

        # Get the avatar name & armature
        avatar_armature = get_avatar_armature(avatar_name)
        if not avatar_armature:
            raise Exception("Armature not found for avatar: " + avatar_name)

        # Copy it to temp scene
        avatar_armature_copy = avatar_armature.copy()
        avatar_armature_copy.data = avatar_armature.data.copy()
        temp_scene.collection.objects.link(avatar_armature_copy)

        # transform_apply(...)
        bpy.context.view_layer.objects.active = avatar_armature_copy
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        # Renamer it
        unrename_info.extend(rename_object(avatar_armature_copy, "Armature"))

        # Merge meshes that are configured to the same layer
        for layer_name in avatar_meshes_layers:
            layer = avatar_meshes_layers[layer_name]

            first_visit = True

            for mesh_name in layer:
                mesh = layer[mesh_name]

                # Copy it to temp scene
                mesh_copy = mesh.copy()
                mesh_copy.data = mesh.data.copy()
                layer[mesh_name] = mesh_copy
                temp_scene.collection.objects.link(mesh_copy)

                # If first time on this layer, renamer it
                if first_visit:
                    unrename_info.extend(rename_object(mesh_copy, layer_name))
                    first_visit = False

                # Merge it to the layer to apply the modifiers
                merge_onto_avatar_layer(layer_name, mesh_copy, avatar_armature_copy)

            # Optimize meshes
            cleanup_mesh(temp_scene.objects[layer_name])

        finalize_and_export(avatar_name, avatar_armature_copy, PROP_AVATAR_EXPORT_PATH, export_format, unrename_info)

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


def finalize_and_export(avatar_name, armature, export_path, export_format, unrename_info):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    # We are already in the temp scene context
    temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)

    path = get_prop(armature, export_path)
    if path:
        if export_format == "fbx":
            path = resolve_path(path, armature.name + ".fbx")

            bpy.ops.export_scene.fbx(
                filepath=path,
                check_existing=False,
                filter_glob="*.fbx",
                use_active_collection=True,
                apply_scale_options="FBX_SCALE_UNITS",
                axis_forward="-Y",
                axis_up="Z",
                use_mesh_modifiers=False,
                mesh_smooth_type="FACE",
                # primary_bone_axis="X",
                # secondary_bone_axis="-Y",
                add_leaf_bones=False,
                bake_anim=False
                # bake_anim_use_all_actions=False,
            )

        elif export_format == "obj":
            path = resolve_path(path, armature.name + ".obj")

            bpy.ops.export_scene.obj(
                filepath=path,
                check_existing=False,
                filter_glob="*.obj",
            )

        elif export_format == "votv":
            clean_avatar_name = sanitize_name(avatar_name)
            
            # Check if export path already ends with avatar name to avoid double nesting
            if path.endswith(clean_avatar_name):
                # Export path already ends with avatar name, use it directly
                avatar_export_dir = path
            else:
                # Create avatar subdirectory: export_path/avatar_name/avatar_name.obj
                avatar_export_dir = os.path.join(path, clean_avatar_name)
            
            # Use resolve_path to properly handle path normalization and absolute path resolution
            path = resolve_path(avatar_export_dir, clean_avatar_name + ".obj")
            
            # Ensure the export directory exists before attempting to export
            export_dir = os.path.dirname(path)
            os.makedirs(export_dir, exist_ok=True)

            ####################
            # Only 1 mesh allowed. merge everything in Temp.
            
            # Deselect all first
            bpy.ops.object.select_all(action='DESELECT')
            
            # Make initial mesh selection by avatar name
            target_obj = None
            first_obj = None
            for obj in temp_scene.objects:
                if obj.type == "MESH":
                    if obj.name == clean_avatar_name:
                        target_obj = obj
                        break
                    elif first_obj is None:
                        first_obj = obj

            if target_obj is None:
                target_obj = first_obj

            if target_obj.name != clean_avatar_name:
                unrename_info.extend(rename_object(target_obj, clean_avatar_name))

            # Now merge the rest of the objects onto mesh avatar name
            for obj in temp_scene.objects:
                if obj.type == "MESH":
                    obj.select_set(True)
            
            # Join onto the active object (avatar name)
            bpy.context.view_layer.objects.active = target_obj
            bpy.ops.object.join()

            bpy.ops.object.select_all(action='DESELECT')

            ####################
            # Sanitize object and material names

            for mat in target_obj.data.materials:
                sanitized_name = sanitize_name(mat.name)
                unrename_info.extend(rename_material(mat, sanitized_name))

            print(unrename_info)

            ####################
            # Triangulate and export the object and UCX object
            
            # Triangulate the object
            bpy.context.view_layer.objects.active = target_obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.quads_convert_to_tris()
            bpy.ops.object.mode_set(mode='OBJECT')

            # Copy all UCX_* objects to the scene
            ucx_objects = [obj for obj in bpy.data.objects if obj.name.startswith("UCX_")]
            if ucx_objects:
                for ucx_object in ucx_objects:
                    ucx_object_copy = ucx_object.copy()
                    ucx_object_copy.data = ucx_object.data.copy()
                    temp_scene.collection.objects.link(ucx_object_copy)
                    
                    # Triangulate the UCX object
                    bpy.context.view_layer.objects.active = ucx_object_copy
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.quads_convert_to_tris()
                    bpy.ops.object.mode_set(mode='OBJECT')
            else:
                raise Exception("Missing collision objects. Make sure there are objects named UCX_*")

            bpy.ops.wm.obj_export(
                filepath=path,
                check_existing=False,
                filter_glob="*.obj",
                global_scale=100.0,
            )

            ####################
            # Separate meshes by material slots
            
            # Remove all UCX objects first - we don't need them for baking
            ucx_objects = [obj for obj in temp_scene.objects if obj.name.startswith("UCX_")]
            for ucx_object in ucx_objects:
                bpy.data.objects.remove(ucx_object)
            
            # Separate mesh by materials using built-in operator
            bpy.ops.object.select_all(action='DESELECT')
            target_obj.select_set(True)
            bpy.context.view_layer.objects.active = target_obj
            
            # Enter edit mode, select all, and separate by material
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.separate(type='MATERIAL')
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # Get all remaining mesh objects (these are our separated single-material objects)
            bake_objects = [obj for obj in temp_scene.objects if obj.type == 'MESH']

            # Material Baker - Bake and pack channels
            debug_print("\n")

            
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
                mat_name = mat.name
                
                # Show only this object for baking and restore its material
                if bake_obj.name in object_states:
                    original_material = object_states[bake_obj.name]
                    enable_render(bake_obj, original_material)

                debug_print("\n")
                debug_print(f"📦 Material: {mat_name}")
                
                principled = find_principled_bsdf(mat)
                
                if not principled:
                    debug_print("❌ No Principled BSDF found")
                    continue
                
                debug_print(f"🔍 Found Principled BSDF: {principled.name}")
                
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
                debug_print(f"    Sockets:")
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
                            debug_print(f"        {pack_name}: {max_resolution[0]}x{max_resolution[1]} (detected)")
                        else:
                            pack_resolutions[pack_name] = (512, 512)
                            debug_print(f"        {pack_name}: 512x512 (default - has input but no textures)")
                    else:
                        pack_resolutions[pack_name] = (8, 8)
                        debug_print(f"        {pack_name}: 8x8 (all defaults)")
                
                # Bake all sockets using pack resolution
                for pack_name, sockets in socket_groups.items():
                    resolution = pack_resolutions[pack_name]
                    
                    for socket_name, key, is_normal in sockets:
                        socket = principled.inputs.get(socket_name)
                        if not socket:
                            continue
                        
                        debug_print(f"🔧 Baking {socket_name}: {resolution[0]}x{resolution[1]} (from {pack_name} pack)")
                        
                        # Determine default value for this socket type
                        default_val = None
                        if is_normal:
                            # Normal maps default to flat normal (0.5, 0.5, 1.0)
                            default_val = (0.5, 0.5, 1.0)
                        elif not has_socket_input(socket) and hasattr(socket, 'default_value'):
                            value = socket.default_value
                            if isinstance(value, (tuple, list)) and len(value) >= 3:
                                debug_print(f"Value: RGB({value[0]:.3f}, {value[1]:.3f}, {value[2]:.3f})")
                            else:
                                debug_print(f"Value: {value}")
                            
                            # Special case: Check for unused emission (strength <= 0)
                            if socket_name == 'Emission Color':
                                emission_strength_socket = principled.inputs.get('Emission Strength')
                                
                                # Check if emission strength is 0 or less (unused)
                                is_unused_emission = False
                                if emission_strength_socket:
                                    has_strength_input = has_socket_input(emission_strength_socket)
                                    
                                    if not has_strength_input:
                                        strength_value = emission_strength_socket.default_value
                                        is_unused_emission = strength_value <= 0.0
                                
                                if is_unused_emission:
                                    # Emission strength is 0 or less, treat as unused
                                    default_val = (0.0, 0.0, 0.0)
                                    debug_print(f"🔧 Emission strength <= 0, overriding to black (unused)")
                                else:
                                    default_val = value
                            else:
                                default_val = value
                        
                        # Bake to memory
                        baked_img = bake_socket(
                            mat,
                            bake_obj,
                            socket_name,
                            resolution,
                            is_normal,
                            default_val
                        )
                        
                        if baked_img:
                            baked_images[key] = baked_img
                            debug_print(f"🍞 Baked successfully")
                        else:
                            debug_print(f"❌ Baking failed")
                
                # Pack and save final textures
                debug_print(f"📦 Packing channels:")
                
                # 1. Diffuse: RGB (Base Color) + Alpha
                diffuse_img = pack_rgba(
                    baked_images.get('base_color'),
                    baked_images.get('alpha'),
                    default_rgb=(1.0, 1.0, 1.0),
                    default_alpha=1.0
                )
                diffuse_path = os.path.join(export_dir, f"diffuse_{mat_name}.png")
                if save_image_as_png(diffuse_img, diffuse_path):
                    debug_print(f"💾 Saved: diffuse_{mat_name}.png")
                else:
                    debug_print(f"❌ Failed to save: diffuse_{mat_name}.png")
                
                # 2. PBR: R (Metallic) + G (Specular) + B (Roughness)
                pbr_img = pack_pbr(
                    baked_images.get('metallic'),
                    baked_images.get('specular'),
                    baked_images.get('roughness'),
                    default_metallic=0.0,
                    default_specular=0.5,
                    default_roughness=0.5
                )
                pbr_path = os.path.join(export_dir, f"pbr_{mat_name}.png")
                if save_image_as_png(pbr_img, pbr_path):
                    debug_print(f"💾 Saved: pbr_{mat_name}.png")
                else:
                    debug_print(f"❌ Failed to save: pbr_{mat_name}.png")
                
                # 3. Normal: RGB (Normal map)
                if 'normal' in baked_images:
                    normal_path = os.path.join(export_dir, f"normal_{mat_name}.png")
                    if save_image_as_png(baked_images['normal'], normal_path):
                        debug_print(f"💾 Saved: normal_{mat_name}.png")
                    else:
                        debug_print(f"❌ Failed to save: normal_{mat_name}.png")
                
                # 4. Emissive: RGB (Emission Color)
                if 'emission' in baked_images:
                    emission_path = os.path.join(export_dir, f"emissive_{mat_name}.png")
                    if save_image_as_png(baked_images['emission'], emission_path):
                        debug_print(f"💾 Saved: emissive_{mat_name}.png")
                    else:
                        debug_print(f"❌ Failed to save: emissive_{mat_name}.png")

                # Clean up any remaining baked images from memory
                for key, img in baked_images.items():
                    if img:
                        try:
                            # Check if image still exists (might have been removed by save_image_as_png)
                            if img.name in bpy.data.images:
                                bpy.data.images.remove(img)
                        except ReferenceError:
                            # Image already removed, skip
                            pass
                
                # Hide this object after baking and clear its material again
                disable_render(bake_obj)

            # Write properties.cfg file
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
                with open(properties_cfg_path, 'w', newline='\n') as f:
                    f.write(properties_content)
                debug_print(f"✅ Created: properties.cfg")
                
            debug_print("\n")
            debug_print("Material Baking Complete")
            debug_print("\n")

    else:
        raise Exception("Export path not found for armature: " + armature.name)


def sanitize_name(name):
    return re.sub(r'[^a-zA-Z0-9\-_]', '_', name)

