import traceback
import bpy
from bpy.props import StringProperty

from .perform_merge_export import perform_merge_export


class NyaaToolsAvatarMergeTool(bpy.types.Operator):
    """Merge and export the avatar. If you have an export path defined, it will export there"""
    bl_idname = "nyaa.avatar_merge_tool"
    bl_label = "Merge & Export"
    bl_options = {"REGISTER", "UNDO"}

    avatar_name: StringProperty(
        name="Avatar Name",
        default=""
    )

    def execute(self, context):
        try:
            perform_merge_export(self.avatar_name)
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        return {"FINISHED"}
