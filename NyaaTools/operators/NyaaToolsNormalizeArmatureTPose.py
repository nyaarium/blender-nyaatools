import bpy
import traceback

from .perform_normalize_armature import perform_normalize_armature


class NyaaToolsNormalizeArmatureTPose(bpy.types.Operator):
    """Normalizes armatures to my preferred T-Pose layout"""
    bl_idname = "nyaa.normalize_armature_t_pose"
    bl_label = "T-Pose"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            perform_normalize_armature("t-pose")
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
