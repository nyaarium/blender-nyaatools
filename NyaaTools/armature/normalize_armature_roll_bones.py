import math
import bpy

from ..bone_desc_map import BONE_DESC_MAP
from ..consts import A_POSE_SHOULDER_ANGLE


def normalize_armature_roll_bones(
    armature: bpy.types.Armature, which_pose, apply_roll=False
):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    if not isinstance(apply_roll, bool):
        raise Exception("apply_roll must be a boolean")

    debug_print("Starting normalize_armature_roll_bones()")

    # Switch to edit mode
    bpy.ops.object.mode_set(mode="EDIT")

    # Iterate over descriptors in BONE_DESC_MAP & reset their roll
    for bone_desc_name in BONE_DESC_MAP:
        bone_desc = BONE_DESC_MAP[bone_desc_name]

        if not bone_desc_name in armature.data.edit_bones:
            continue

        # Get bone
        bone = armature.data.edit_bones[bone_desc_name]

        # Clear roll instead if !apply_roll
        if not apply_roll:
            debug_print("Clearing roll of", bone.name)
            bone.roll = 0
            continue

        desc_roll = 0

        if "roll" in bone_desc and bone_desc["roll"] != None:
            desc_roll = bone_desc["roll"]

        if which_pose == "a-pose":
            sw = bone_desc_name.startswith

            # Shoulder
            if sw("Shoulder"):
                r = A_POSE_SHOULDER_ANGLE
                if bone_desc_name.endswith(".R"):
                    r *= -1
                desc_roll += r
                debug_print("For A-Pose, shoulder", desc_roll)

            # Arm and below:
            if (
                sw("Upper Arm")
                or sw("Lower Arm")
                or sw("Hand")
                or sw("Thumb")
                or sw("Index")
                or sw("Middle")
                or sw("Ring")
                or sw("Little")
            ):
                r = 45
                if bone_desc_name.endswith(".R"):
                    r *= -1
                desc_roll += r
                debug_print("For A-Pose, arm and below", desc_roll)

        if bone.roll != desc_roll:
            debug_print("Setting roll of", bone.name, "to", desc_roll)
            bone.roll = math.radians(desc_roll)
