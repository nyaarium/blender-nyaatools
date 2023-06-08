import bpy

from ..armature.estimate_is_normalized import estimate_is_normalized
from ..armature.normalize_armature_pose import normalize_armature_pose


def perform_fast_pose(which_pose):
    if not which_pose in ["a-pose", "t-pose"]:
        raise Exception("which_pose must be a-pose or t-pose")

    armature = bpy.context.active_object

    if armature == None:
        raise Exception("Please select an armature object first! Got: None")

    if armature.type != "ARMATURE":
        raise Exception(
            "Please select an armature object first! Got: " + armature.type)

    if estimate_is_normalized(armature):
        normalize_armature_pose(armature, which_pose, False)
    else:
        raise Exception("Armature is not normalized! Please normalize first.")
