import traceback
import bpy
from bpy.props import StringProperty

from .perform_configure_avatar_armature import perform_configure_avatar_armature


class NyaaToolsConfigureAvatarArmature(bpy.types.Operator):
    """Configure this armature as an Avatar"""
    bl_idname = "nyaa.configure_avatar_armature"
    bl_label = "Configure Avatar"
    bl_options = {"REGISTER", "UNDO"}

    avatar_name: StringProperty(name="Avatar Name", default="")
    export_path: StringProperty(name="Export Path", default="Export.fbx")

    def execute(self, context):
        try:
            perform_configure_avatar_armature(
                avatar=self.avatar_name,
                export_path=self.export_path,
            )
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
