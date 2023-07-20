import traceback
import bpy
from bpy.props import BoolProperty

from ..common.selection_get_armature import selection_get_armature
from ..bone_desc_map import BONE_DESC_MAP


class NyaaSelectStandardBones(bpy.types.Operator):
    """Select only the standard bones of a humanoid armature. Must be Nyaa Normalized."""

    bl_idname = "nyaa.select_standard_bones"
    bl_label = "Select standard bones (in edit or pose mode)"
    bl_options = {"REGISTER", "UNDO"}

    include_breast_bones: BoolProperty(
        name="Include Breasts",
        description="Include breast bones in selection",
        default=True,
    )

    def execute(self, context):
        try:
            armature = selection_get_armature()

            perform_select_standard_bones(
                armature, include_breast_bones=self.include_breast_bones
            )

            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_select_standard_bones(armature, include_breast_bones=True):
    if armature == None or armature.type != "ARMATURE":
        raise Exception("Expected an armature")

    currentMode = bpy.context.mode

    if currentMode == "EDIT_ARMATURE":
        bpy.ops.armature.select_all(action="DESELECT")

        # Loop over names in BONE_DESC_MAP and select just those edit bones
        for bone_desc_name in BONE_DESC_MAP:
            if bone_desc_name not in armature.data.edit_bones:
                raise Exception(
                    bone_desc_name + " not found. Is this armature Nyaa Normalized?"
                )

            eb = armature.data.edit_bones[bone_desc_name]

            if bone_desc_name.startswith("Breast"):
                if include_breast_bones:
                    eb.select = True
            else:
                eb.select = True

    elif currentMode == "POSE":
        bpy.ops.pose.select_all(action="DESELECT")

        # Loop over names in BONE_DESC_MAP and select just those pose bones
        for bone_desc_name in BONE_DESC_MAP:
            if bone_desc_name not in armature.pose.bones:
                raise Exception(
                    bone_desc_name + " not found. Is this armature Nyaa Normalized?"
                )

            pb = armature.pose.bones[bone_desc_name]

            if bone_desc_name.startswith("Breast"):
                if include_breast_bones:
                    pb.bone.select = True
            else:
                pb.bone.select = True

    else:
        raise Exception("Switch to edit or pose mode first")
