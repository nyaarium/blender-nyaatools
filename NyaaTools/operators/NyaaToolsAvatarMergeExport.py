import traceback
import bpy
from bpy.props import StringProperty

from ..mesh.cleanup_mesh import cleanup_mesh
from ..consts import EXPORT_COLLECTION, PROP_AVATAR_EXPORT_PATH
from ..common.deselect_all import deselect_all
from ..common.get_prop import get_prop
from ..common.renamer_rename import renamer_rename
from ..common.renamer_restore import renamer_restore
from ..common.resolve_path import resolve_path
from ..common.select_collection import select_collection
from ..common.selection_add import selection_add
from ..avatar.find_scene_avatars import find_scene_avatars
from ..avatar.get_avatar_armature import get_avatar_armature
from ..avatar.get_avatar_layers import get_avatar_layers
from ..avatar.get_avatar_meshes import get_avatar_meshes
from ..avatar.merge_onto_avatar_layer import merge_onto_avatar_layer


TEMP_SCENE_NAME = "Temp Merge & Export"


class NyaaToolsAvatarMergeExport(bpy.types.Operator):
    """Merge and export the avatar. If you have an export path defined, it will export there"""

    bl_idname = "nyaa.avatar_merge_export"
    bl_label = "Merge & Export"
    bl_options = {"REGISTER", "UNDO"}

    avatar_name: StringProperty(name="Avatar Name", default="")
    # TODO: additional options

    def execute(self, context):
        try:
            if not self.avatar_name:
                self.report({"ERROR"}, "Specify an avatar name.")
                return {"CANCELLED"}

            perform_merge_export(
                self.avatar_name,
                # TODO: additional options
            )

            armature = get_avatar_armature(self.avatar_name)
            path = get_prop(armature, PROP_AVATAR_EXPORT_PATH)
            if path:
                path = resolve_path(path, self.avatar_name + ".fbx")

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


def perform_merge_export(avatar_name):
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

    try:
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
        unrename_info.extend(renamer_rename(avatar_armature_copy, "Armature"))

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
                    unrename_info.extend(renamer_rename(mesh_copy, layer_name))
                    first_visit = False

                # Merge it to the layer to apply the modifiers
                merge_onto_avatar_layer(layer_name, mesh_copy, avatar_armature_copy)

            # Optimize meshes
            cleanup_mesh(temp_scene.objects[layer_name])

        # Export
        path = get_prop(avatar_armature_copy, PROP_AVATAR_EXPORT_PATH)
        if path:
            path = resolve_path(path, avatar_name + ".fbx")
            export_fbx(path)

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


def export_fbx(path):
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
