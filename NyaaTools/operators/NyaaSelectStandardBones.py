import bpy
import traceback

from ..common.selection_get_armature import selection_get_armature
from ..bone_desc_map import BONE_DESC_MAP


class NyaaSelectStandardBones(bpy.types.Operator):
    """Select standard bones"""

    bl_idname = "nyaa.select_standard_bones"
    bl_label = "Select standard bones (in edit or pose mode)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            armature = selection_get_armature()

            perform_select_standard_bones(armature)

            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_select_standard_bones(armature):
    if armature == None or armature.type != "ARMATURE":
        raise Exception("Expected an armature")

    currentMode = bpy.context.mode

    if currentMode == "EDIT_ARMATURE":
        bpy.ops.armature.select_all(action="DESELECT")

        # Loop over names in BONE_DESC_MAP and select just those edit bones
        for bone_desc_name in BONE_DESC_MAP:
            eb = armature.data.edit_bones[bone_desc_name]
            eb.select = True

    elif currentMode == "POSE":
        bpy.ops.pose.select_all(action="DESELECT")

        # Loop over names in BONE_DESC_MAP and select just those pose bones
        for bone_desc_name in BONE_DESC_MAP:
            pb = armature.pose.bones[bone_desc_name]
            pb.bone.select = True

    else:
        raise Exception("Switch to edit or pose mode first")
