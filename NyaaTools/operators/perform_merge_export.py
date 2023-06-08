import bpy

from ..avatar.get_avatar_armature import get_avatar_armature
from ..avatar.get_avatar_layers import get_avatar_layers
from ..avatar.get_avatar_meshes import get_avatar_meshes
from ..avatar.merge_onto_avatar_layer import merge_onto_avatar_layer
from ..common.get_prop import get_prop
from ..common.select_collection import select_collection
from ..common.selection_add import selection_add
from ..consts import EXPORT_COLLECTION, PROP_AVATAR_EXPORT_PATH
from ..mesh.cleanup_mesh import cleanup_mesh


def perform_merge_export(avatar_name):
    armature = get_avatar_armature(avatar_name)

    # Create "Export" collection
    export_collection = bpy.data.collections.new("Export")

    bpy.context.scene.collection.children.link(export_collection)
    export_collection.color_tag = "COLOR_01"

    # Rename all objects to avoid collisions
    for obj in bpy.data.objects:
        obj.name = "____" + obj.name

    # Rename & move Armature to exports
    armature.name = "Armature"
    armature.data.name = "Armature"
    armature.parent = None

    try:
        selection_add(armature)
        bpy.ops.object.transform_apply(
            location=True, rotation=True, scale=True)
        bpy.data.collections[EXPORT_COLLECTION].objects.link(armature)
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
                    merge_onto_avatar_layer(
                        path_layer_name, meshName, armature)

        else:
            print("    BUG: Mesh doesn't exist, skipping for now:  " + meshName)

    # Cleanup temp objects
    for obj in bpy.data.objects:
        if (obj.name.startswith("____")):
            bpy.data.objects.remove(obj)

    # Optimize meshes
    for obj in bpy.data.objects:
        if (obj.type == "MESH"):
            cleanup_mesh(obj)

    for col in bpy.context.scene.collection.children:
        if (col.name != "Export"):
            bpy.data.collections.remove(col)

    # Export
    select_collection(EXPORT_COLLECTION)

    if get_prop(armature, PROP_AVATAR_EXPORT_PATH):
        path = get_prop(armature, PROP_AVATAR_EXPORT_PATH)
        if (path):
            if (path[-1] == "/" or path[-1] == "\\"):
                path = bpy.path.abspath(
                    "//" + path + path_avatar_name + ".fbx")
            else:
                path = bpy.path.abspath("//" + path)

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
