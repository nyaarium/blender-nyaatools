import bpy
from bpy.props import StringProperty
import traceback

from ..avatar.add_to_avatar_layer import add_to_avatar_layer
from ..avatar.get_avatar_armature import get_avatar_armature
from ..common.get_prop import get_prop
from ..common.has_value import has_value
from ..common.selection_get_armature import selection_get_armature
from ..common.selection_get_meshes import selection_get_meshes
from ..consts import PROP_AVATAR_NAME


class NyaaToolsConfigureMeshesOnAvatar(bpy.types.Operator):
    """Configure meshes on avatar"""
    bl_idname = "nyaa.configure_meshes_on_avatar"
    bl_label = "Add Meshes to Avatar"
    bl_options = {"REGISTER", "UNDO"}

    layer_name: StringProperty(name="Layer Name", default="")

    def execute(self, context):
        try:
            if not has_value(self.layer_name):
                self.report({"INFO"}, "Please enter a layer name")
                return {"FINISHED"}

            armature = selection_get_armature()
            meshes = selection_get_meshes()

            perform_add_meshes_to_avatar(
                armature,
                meshes,
                self.layer_name,
            )
            self.report({"INFO"},
                        str(len(meshes)) + " assigned to " + self.layer_name)
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_add_meshes_to_avatar(armature, meshes, layer_name):
    if not isinstance(meshes, list) or len(meshes) == 0:
        raise Exception("Expected at least one mesh")

    if armature == None or armature.type != "ARMATURE":
        raise Exception("Expected an armature")

    avatar_name = get_prop(armature, PROP_AVATAR_NAME)

    if not has_value(avatar_name):
        raise Exception("Expected an avatar name")

    if not has_value(layer_name):
        raise Exception("Expected a layer name")

    # Add all meshes to the avatar layer
    for mesh in meshes:
        add_to_avatar_layer(avatar_name, layer_name, mesh)
