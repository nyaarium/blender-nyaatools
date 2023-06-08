import traceback
import bpy

from .perform_fast_pose import perform_fast_pose


class NyaaToolsSetArmatureTPose(bpy.types.Operator):
    """Sets armatures to my preferred T-Pose layout"""
    bl_idname = "nyaa.set_armature_t_pose"
    bl_label = "T-Pose"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            perform_fast_pose("t-pose")
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
