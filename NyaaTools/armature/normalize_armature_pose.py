
import math
import bpy

from .align_bone_to_axis import align_bone_to_axis
from .apply_pose import apply_pose
from .clear_pose import clear_pose
from .find_bone import find_bone
from .find_meshes_affected_by_armature_modifier import find_meshes_affected_by_armature_modifier
from ..consts import A_POSE_SHOULDER_ANGLE


def normalize_armature_pose(armature: bpy.types.Armature, which_pose, apply_rest_pose, callback_progress_tick=None):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    debug_print("Starting normalize_armature_pose()")

    # Find all meshes that have an armature modifier with this armature
    affected_meshes = find_meshes_affected_by_armature_modifier(armature)

    clear_pose(armature)

    should_apply = False

    ################
    # Ankle Initialization - Point Ankle bone forward without affecting pose

    if align_bone_to_axis(armature, find_bone("edit", armature, "Foot.L"), 0, -1, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    if align_bone_to_axis(armature, find_bone("edit", armature, "Toes.L"), 0, -1, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align ankle to y-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Foot.L"), 0, -1, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    ################
    # Body Round 1

    # Edit move hips to thigh's yz-plane
    hips = find_bone("edit", armature, "Hips")
    thigh = find_bone("edit", armature, "Upper Leg.L")
    if thigh.matrix.translation.z != 0:
        thigh.matrix.translation.z = 0
        hips.head.y = thigh.matrix.translation.y
        hips.head.z = thigh.matrix.translation.z
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align hips to z-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Hips"), 0, 0, 1):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Move hips to y=0
    hips = find_bone("pose", armature, "Hips")
    if hips.matrix.translation.y != 0:
        hips.matrix.translation.y = 0
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    ################
    # Body Round 2

    # Align spine to z-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Spine"), 0, 0, 1):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # # Align thigh to z-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Upper Leg.L"), 0, 0, -1):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Move thigh to y=0
    thigh_l = find_bone("pose", armature, "Upper Leg.L")
    thigh_r = find_bone("pose", armature, "Upper Leg.R")
    if thigh_l.matrix.translation.y != 0:
        thigh_l.matrix.translation.y = 0
        thigh_r.matrix.translation.y = 0
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    ################
    # Body Round 3

    # Align chest to z-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Chest"), 0, 0, 1):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align knee to z-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Lower Leg.L"), 0, 0, -1):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    ################
    # Body Round 4

    # Align neck to z-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Neck"), 0, 0, 1):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Move neck to z=0
    neck = find_bone("pose", armature, "Neck")
    if neck.matrix.translation.y != 0:
        neck.matrix.translation.y = 0
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Move shoulder to z=0
    shoulder_l = find_bone("pose", armature, "Shoulder.L")
    shoulder_r = find_bone("pose", armature, "Shoulder.R")
    if shoulder_l.matrix.translation.y != 0 or shoulder_r.matrix.translation.y != 0:
        shoulder_l.matrix.translation.y = 0
        shoulder_r.matrix.translation.y = 0
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align ankle to y-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Foot.L"), 0, -1, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    ################
    # Body Round 5

    # Align head to z-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Head"), 0, 0, 1):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align toes to y-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Toes.L"), 0, -1, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    ################
    # The rest of the arm

    # Align shoulder to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Shoulder.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align upper arm to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Upper Arm.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align elbow to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Lower Arm.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align wrist to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Hand.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    ################
    # Fingers Round 1

    # Align "Thumb 1" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Thumb 1.L"), 1, -1, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Index Finger 1" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Index Finger 1.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Middle Finger 1" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Middle Finger 1.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Ring Finger 1" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Ring Finger 1.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Little Finger 1" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Little Finger 1.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    ################
    # Fingers Round 2

    # Align "Thumb 2" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Thumb 2.L"), 1, -1, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Index Finger 2" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Index Finger 2.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Middle Finger 2" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Middle Finger 2.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Ring Finger 2" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Ring Finger 2.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Little Finger 2" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Little Finger 2.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    ################
    # Fingers Round 3

    # Align "Thumb 3" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Thumb 3.L"), 1, -1, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Index Finger 3" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Index Finger 3.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Middle Finger 3" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Middle Finger 3.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Ring Finger 3" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Ring Finger 3.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Little Finger 3" to x-axis
    if align_bone_to_axis(armature, find_bone("pose", armature, "Little Finger 3.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # A-Pose only
    if which_pose == "a-pose":
        a = A_POSE_SHOULDER_ANGLE
        z = math.sin(math.radians(a)) / math.sin(math.radians(90 - a))

        align_bone_to_axis(armature, find_bone(
            "pose", armature, "Shoulder.L"), 1, 0, -z)
        align_bone_to_axis(armature, find_bone(
            "pose", armature, "Upper Arm.L"), 1, 0, -1)
        # dont callback tick since this is a dynamic choice

    ################

    bpy.ops.object.mode_set(mode="POSE")

    # Apply to all meshes / shape keys
    if apply_rest_pose and should_apply:
        apply_pose(armature, affected_meshes, callback_progress_tick)
        clear_pose(armature)
