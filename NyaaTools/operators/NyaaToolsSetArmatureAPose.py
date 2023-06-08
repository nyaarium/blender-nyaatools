import traceback
import bpy

from .perform_fast_pose import perform_fast_pose


class NyaaToolsSetArmatureAPose(bpy.types.Operator):
    """Sets armatures to my preferred A-Pose layout"""
    bl_idname = "nyaa.set_armature_a_pose"
    bl_label = "A-Pose"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            perform_fast_pose("a-pose")
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
