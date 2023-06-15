import traceback
import bpy
from bpy.props import StringProperty

from ..avatar.get_avatar_armature import get_avatar_armature
from ..common.get_prop import get_prop
from ..common.has_value import has_value
from ..common.selection_get_armature import selection_get_armature
from ..common.selection_get_meshes import selection_get_meshes
from ..common.set_prop import set_prop
from ..consts import PROP_AVATAR_EXPORT_PATH, PROP_AVATAR_NAME


class NyaaToolsConfigureAvatarArmature(bpy.types.Operator):
    """Configure this armature as an Avatar"""
    bl_idname = "nyaa.configure_avatar_armature"
    bl_label = "Configure Avatar"
    bl_options = {"REGISTER", "UNDO"}

    avatar_name: StringProperty(name="Avatar Name", default="")
    export_path: StringProperty(name="Export Path", default="Export.fbx")

    def execute(self, context):
        try:
            if not has_value(self.avatar_name):
                self.report({"INFO"}, "Please enter an avatar name")
                return {"FINISHED"}

            armature = selection_get_armature()

            perform_configure_avatar_armature(
                armature,
                self.avatar_name,
                self.export_path
            )
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_configure_avatar_armature(armature, avatar_name, export_path):
    if armature == None or armature.type != "ARMATURE":
        raise Exception("Expected an armature")

    # TODO: Check if avatar name already exists. Error if it does

    set_prop(armature, PROP_AVATAR_NAME, avatar_name)
    set_prop(armature, PROP_AVATAR_EXPORT_PATH, export_path)

    # TODO: Rename all existing mesh layers of this avatar (remove layer, then add layer)
