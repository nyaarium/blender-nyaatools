import math
import bpy
from mathutils import Vector

from .align_bone_to_axis import align_bone_to_axis as abta
from .apply_pose import apply_pose
from .clear_pose import clear_pose
from .find_bone import find_bone
from .find_meshes_affected_by_armature_modifier import (
    find_meshes_affected_by_armature_modifier,
)
from ..common.deselect_all import deselect_all
from ..common.selection_add import selection_add
from ..consts import A_POSE_SHOULDER_ANGLE


def normalize_armature_pose(
    armature: bpy.types.Armature,
    which_pose,
    apply_rest_pose,
    callback_progress_tick=None,
):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    debug_print("Starting normalize_armature_pose()")

    #################
    # Find all meshes that have an armature modifier with this armature
    affected_meshes = find_meshes_affected_by_armature_modifier(armature)
    total_shapekeys = 0
    for mesh, modifier in affected_meshes:
        # Show in viewport
        selection_add(mesh)
        modifier.show_viewport = True
        modifier.use_deform_preserve_volume = True
        mesh.hide_viewport = False

        if mesh.data.shape_keys != None:
            total_shapekeys += len(mesh.data.shape_keys.key_blocks)

        if callback_progress_tick != None:
            callback_progress_tick()

    deselect_all()
    #################

    selection_add(armature)
    clear_pose(armature)

    should_apply = False

    ################
    # Ankle Initialization - Point Ankle bone forward without affecting pose

    if abta(armature, find_bone("edit", armature, "Foot.L"), 0, -1, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align ankle to y-axis

    eb_toes_l = find_bone("edit", armature, "Toes.L")
    if eb_toes_l:
        if abta(armature, eb_toes_l, 0, -1, 0):
            should_apply = True
        if callback_progress_tick != None:
            callback_progress_tick()

    eb_toes_r = find_bone("edit", armature, "Toes.R")
    if eb_toes_r:
        if abta(armature, eb_toes_r, 0, -1, 0):
            should_apply = True
        if callback_progress_tick != None:
            callback_progress_tick()

    ################
    # Arm

    # Align shoulder to x-axis
    if abta(armature, find_bone("pose", armature, "Shoulder.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align upper arm to x-axis
    if abta(armature, find_bone("pose", armature, "Upper Arm.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align elbow to x-axis
    if abta(armature, find_bone("pose", armature, "Lower Arm.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align wrist to x-axis
    if abta(armature, find_bone("pose", armature, "Hand.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    ################
    # Shoulder Realignment - Make a temp bone for later

    if apply_rest_pose:
        pb_shoulder_y = find_bone("pose", armature, "Shoulder.L").head.y
        pb_shoulder_z = find_bone("pose", armature, "Shoulder.L").head.z

        bpy.ops.object.mode_set(mode="EDIT")
        eb_realign_shoulder = armature.data.edit_bones.new("__ Shoulder Realign __")

        eb_shoulder_l = find_bone("edit", armature, "Shoulder.L")
        eb_chest = find_bone("edit", armature, "Chest")

        y = eb_shoulder_l.head.y + (eb_shoulder_l.head.y - pb_shoulder_y)
        z = eb_shoulder_l.head.z + (eb_shoulder_l.head.z - pb_shoulder_z)

        eb_realign_shoulder.head = Vector((0, y, z))
        eb_realign_shoulder.tail = Vector((0, y, z + 0.1))
        eb_realign_shoulder.parent = eb_chest

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
    if abta(armature, find_bone("pose", armature, "Hips"), 0, 0, 1):
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
    if abta(armature, find_bone("pose", armature, "Spine"), 0, 0, 1):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align thigh to z-axis
    if abta(armature, find_bone("pose", armature, "Upper Leg.L"), 0, 0, -1):
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
    if abta(armature, find_bone("pose", armature, "Chest"), 0, 0, 1):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align knee to z-axis
    if abta(armature, find_bone("pose", armature, "Lower Leg.L"), 0, 0, -1):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    ################
    # Body Round 4

    neck = find_bone("pose", armature, "Neck")

    # Move neck to z=0
    if neck.matrix.translation.y != 0:
        neck.matrix.translation.y = 0
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align neck to z-axis
    if abta(armature, neck, 0, 0, 1):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Move shoulder to z=0
    pb_shoulder_l = find_bone("pose", armature, "Shoulder.L")
    pb_shoulder_r = find_bone("pose", armature, "Shoulder.R")
    if (
        pb_shoulder_l.matrix.translation.y != 0
        or pb_shoulder_r.matrix.translation.y != 0
    ):
        pb_shoulder_l.matrix.translation.y = 0
        pb_shoulder_r.matrix.translation.y = 0
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align ankle to y-axis
    if abta(armature, find_bone("pose", armature, "Foot.L"), 0, -1, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    ################
    # Body Round 5

    # Align head to z-axis
    if abta(armature, find_bone("pose", armature, "Head"), 0, 0, 1):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align toes to y-axis
    pb_toes_l = find_bone("pose", armature, "Toes.L")
    if pb_toes_l:
        if abta(armature, pb_toes_l, 0, -1, 0):
            should_apply = True
        if callback_progress_tick != None:
            callback_progress_tick()

    ################
    # Shoulder Realignment - Temporarily attach to realign_temp_bone

    if apply_rest_pose:
        bpy.ops.object.mode_set(mode="EDIT")
        eb_realign_shoulder = armature.data.edit_bones["__ Shoulder Realign __"]
        eb_shoulder_l = find_bone("edit", armature, "Shoulder.L")
        eb_shoulder_r = find_bone("edit", armature, "Shoulder.R")
        eb_shoulder_l.parent = eb_realign_shoulder
        eb_shoulder_r.parent = eb_realign_shoulder

        bpy.ops.object.mode_set(mode="POSE")
        pb_realign_shoulder = armature.pose.bones["__ Shoulder Realign __"]
        if abta(armature, pb_realign_shoulder, 0, 0, 1):
            should_apply = True

    ################
    # Fingers Round 1

    # Align "Thumb 1" to x-axis
    if abta(armature, find_bone("pose", armature, "Thumb 1.L"), 1, -1, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Index Finger 1" to x-axis
    if abta(armature, find_bone("pose", armature, "Index Finger 1.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Middle Finger 1" to x-axis
    if abta(armature, find_bone("pose", armature, "Middle Finger 1.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Ring Finger 1" to x-axis
    if abta(armature, find_bone("pose", armature, "Ring Finger 1.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Little Finger 1" to x-axis
    if abta(armature, find_bone("pose", armature, "Little Finger 1.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    ################
    # Fingers Round 2

    # Align "Thumb 2" to x-axis
    if abta(armature, find_bone("pose", armature, "Thumb 2.L"), 1, -1, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Index Finger 2" to x-axis
    if abta(armature, find_bone("pose", armature, "Index Finger 2.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Middle Finger 2" to x-axis
    if abta(armature, find_bone("pose", armature, "Middle Finger 2.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Ring Finger 2" to x-axis
    if abta(armature, find_bone("pose", armature, "Ring Finger 2.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Little Finger 2" to x-axis
    if abta(armature, find_bone("pose", armature, "Little Finger 2.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    ################
    # Fingers Round 3

    # Align "Thumb 3" to x-axis
    if abta(armature, find_bone("pose", armature, "Thumb 3.L"), 1, -1, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Index Finger 3" to x-axis
    if abta(armature, find_bone("pose", armature, "Index Finger 3.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Middle Finger 3" to x-axis
    if abta(armature, find_bone("pose", armature, "Middle Finger 3.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Ring Finger 3" to x-axis
    if abta(armature, find_bone("pose", armature, "Ring Finger 3.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # Align "Little Finger 3" to x-axis
    if abta(armature, find_bone("pose", armature, "Little Finger 3.L"), 1, 0, 0):
        should_apply = True
    if callback_progress_tick != None:
        callback_progress_tick()

    # A-Pose only
    if which_pose == "a-pose":
        a = A_POSE_SHOULDER_ANGLE
        z = math.sin(math.radians(a)) / math.sin(math.radians(90 - a))

        abta(armature, find_bone("pose", armature, "Shoulder.L"), 1, 0, -z)
        abta(armature, find_bone("pose", armature, "Upper Arm.L"), 1, 0, -1)

    ################
    # Apply to all meshes / shape keys

    if apply_rest_pose and should_apply:
        apply_pose(armature, affected_meshes, callback_progress_tick)
        clear_pose(armature)

    ################
    # Shoulder Realignment - Remove temporary realign_temp_bone

    if apply_rest_pose:
        bpy.ops.object.mode_set(mode="EDIT")
        eb_realign_shoulder = armature.data.edit_bones["__ Shoulder Realign __"]
        eb_shoulder_l = find_bone("edit", armature, "Shoulder.L")
        eb_shoulder_r = find_bone("edit", armature, "Shoulder.R")
        eb_chest = find_bone("edit", armature, "Chest")
        eb_shoulder_l.parent = eb_chest
        eb_shoulder_r.parent = eb_chest
        armature.data.edit_bones.remove(eb_realign_shoulder)

    ################
    # Eye Length

    DEFAULT_LENGTH = 0.05
    eb_eye_l = find_bone("edit", armature, "Eye.L")
    eb_eye_r = find_bone("edit", armature, "Eye.R")
    if (eb_eye_l.tail.z - eb_eye_l.head.z) != DEFAULT_LENGTH:
        eb_eye_l.tail.x = eb_eye_l.head.x
        eb_eye_l.tail.y = eb_eye_l.head.y
        eb_eye_l.tail.z = eb_eye_l.head.z + DEFAULT_LENGTH

        eb_eye_r.tail.x = eb_eye_r.head.x
        eb_eye_r.tail.y = eb_eye_r.head.y
        eb_eye_r.tail.z = eb_eye_r.head.z + DEFAULT_LENGTH

    ################
    # Breast Root

    eb_breast_root = find_bone("edit", armature, "Breast Root")
    if eb_breast_root:
        eb_chest = find_bone("edit", armature, "Chest")
        eb_breast_l = find_bone("edit", armature, "Breast.L")

        eb_breast_root.head = (
            0,
            eb_chest.head.y - 0.02,
            eb_breast_l.head.z,
        )

        eb_breast_root.tail = (
            0,
            eb_chest.head.y - 0.02,
            eb_breast_l.head.z + DEFAULT_LENGTH,
        )
