import traceback
import bpy

from .perform_apply_top_modifier import perform_apply_top_modifier


class NyaaToolsApplyTopModifier(bpy.types.Operator):
    """Apply the topmost modifier for object with shape keys (GitHub/przemir)"""
    bl_idname = "nyaa.apply_top_modifier"
    bl_label = "Add Modifier"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            perform_apply_top_modifier()
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
