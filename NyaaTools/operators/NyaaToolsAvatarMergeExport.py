import traceback
import bpy
from bpy.props import StringProperty

from ..mesh.cleanup_mesh import cleanup_mesh
from ..consts import EXPORT_COLLECTION, PROP_AVATAR_EXPORT_PATH
from ..common.deselect_all import deselect_all
from ..common.selection_add import selection_add
from ..common.select_collection import select_collection
from ..common.get_prop import get_prop
from ..avatar.merge_onto_avatar_layer import merge_onto_avatar_layer
from ..avatar.get_avatar_meshes import get_avatar_meshes
from ..avatar.get_avatar_layers import get_avatar_layers
from ..avatar.get_avatar_armature import get_avatar_armature


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
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_merge_export(avatar_name):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    bpy.ops.object.mode_set(mode="OBJECT")

    armature = get_avatar_armature(avatar_name)

    # Show all collections
    for col in bpy.context.scene.collection.children:
        col.hide_viewport = False

    # Create export collection
    export_col = bpy.data.collections.new("__Export Temp__")
    bpy.context.scene.collection.children.link(export_col)
    export_col.color_tag = "COLOR_01"

    # Rename all objects except EMPTYs, to avoid collisions
    for obj in bpy.data.objects:
        if obj.type != "EMPTY":
            obj.name = "____" + obj.name

    # Rename & move Armature to exports
    armature.name = "Armature"
    armature.data.name = "Armature"
    armature.parent = None

    # Link to soon-to-be Export collection
    try:
        selection_add(armature)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.data.collections["__Export Temp__"].objects.link(armature)
    except:
        None

    # Unlink from Scene Collection
    try:
        bpy.context.scene.collection.objects.unlink(armature)
    except:
        None

    # Perform layer merges on meshes
    for meshName in get_avatar_meshes(avatar_name):
        mesh = bpy.context.scene.objects.get(meshName)
        if mesh != None:
            # Get pairs [path_avatar_name, path_layer_name]
            # If avatar_name == path_avatar_name, merge
            layers = get_avatar_layers(mesh)
            for path_avatar_name, path_layer_name in layers:
                if avatar_name == path_avatar_name:
                    merge_onto_avatar_layer(path_layer_name, meshName, armature)

        else:
            print("    BUG: Mesh doesn't exist, skipping for now:  " + meshName)

    # Delete everything else except EMPTYs
    for obj in bpy.data.objects:
        if obj.name.startswith("____"):
            bpy.data.objects.remove(obj)

    # Optimize meshes
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            cleanup_mesh(obj)

    # Purge orphaned data
    bpy.ops.outliner.orphans_purge(do_recursive=True)

    # Export EMPTYs that have users, otherwise delete them
    for obj in bpy.data.objects:
        if obj.type == "EMPTY":
            if obj.users != 1:
                bpy.data.collections["__Export Temp__"].objects.link(obj)
            else:
                bpy.data.objects.remove(obj)

    for col in bpy.context.scene.collection.children:
        if col.name != "__Export Temp__":
            bpy.data.collections.remove(col)

    # Export
    export_col.name = EXPORT_COLLECTION
    select_collection(EXPORT_COLLECTION)

    deselect_all()

    # Purge orphaned data
    bpy.ops.outliner.orphans_purge(do_recursive=True)

    selection_add(armature)

    if get_prop(armature, PROP_AVATAR_EXPORT_PATH):
        path = get_prop(armature, PROP_AVATAR_EXPORT_PATH)
        if path:
            # Replace all slashes
            path = path.replace("\\", "/")

            file_path = ""
            file_name = ""

            # Get path parts
            if path.endswith(".fbx"):
                file_name = path.split("/")[-1]
                file_path = path[: -len(file_name) - 1]
            else:
                file_name = avatar_name + ".fbx"
                file_path = path

            if len(file_path) == 0:
                file_path = "./"

            print(file_path)
            print(file_name)

            # A. Absolute paths (D:\Path)
            # B. Network path (\\Network Path)
            # C. Relative paths
            if 2 <= len(file_path) and file_path[1] == ":":
                path = file_path + "/" + file_name
            elif file_path.startswith("//"):
                path = file_path + "/" + file_name
            else:
                path = bpy.path.abspath("//" + file_path + "/" + file_name)

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
