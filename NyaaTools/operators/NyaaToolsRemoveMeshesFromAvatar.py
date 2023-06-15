import bpy
from bpy.props import StringProperty
import traceback

from ..avatar.get_avatar_armature import get_avatar_armature
from ..avatar.remove_from_avatar_layers import remove_from_avatar_layers
from ..common.get_prop import get_prop
from ..common.has_value import has_value
from ..common.selection_get_armature import selection_get_armature
from ..common.selection_get_meshes import selection_get_meshes
from ..consts import PROP_AVATAR_NAME


class NyaaToolsRemoveMeshesFromAvatar(bpy.types.Operator):
    """Remove meshes from avatar"""
    bl_idname = "nyaa.remove_meshes_from_avatar"
    bl_label = "Remove Meshes from Avatar"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            armature = selection_get_armature()
            meshes = selection_get_meshes()

            perform_remove_meshes_from_avatar(armature, meshes)
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_remove_meshes_from_avatar(armature, meshes):
    if not isinstance(meshes, list) or len(meshes) == 0:
        raise Exception("Expected at least one mesh")

    if armature == None or armature.type != "ARMATURE":
        raise Exception("Expected an armature")

    avatar_name = get_prop(armature, PROP_AVATAR_NAME)

    if not has_value(avatar_name):
        raise Exception("Expected an avatar name")

    # Remove all meshes from the avatar
    for mesh in meshes:
        remove_from_avatar_layers(avatar_name, mesh)
