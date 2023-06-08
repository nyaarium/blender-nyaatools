import bpy
import traceback

from .perform_normalize_armature import perform_normalize_armature


class NyaaToolsNormalizeArmatureAPose(bpy.types.Operator):
    """Normalizes armatures to my preferred A-Pose layout"""
    bl_idname = "nyaa.normalize_armature_a_pose"
    bl_label = "A-Pose"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            perform_normalize_armature("a-pose")
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
