import bpy

from ..armature.normalize_armature_clear_custom_objects import (
    normalize_armature_clear_custom_objects,
)
from ..common.selection_get_armature import selection_get_armature


class NYAATOOLS_OT_NormalizeArmatureClearCustomObjects(bpy.types.Operator):
    """Clear custom objects from the selected armature"""

    bl_idname = "nyaa.armature_clear_custom_objects"
    bl_label = "Armature Clear Custom Objects"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            armature = selection_get_armature()
            if armature is None:
                self.report({"ERROR"}, "No armature selected")
                return {"CANCELLED"}

            normalize_armature_clear_custom_objects(armature)
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
