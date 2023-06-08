import bpy

from ..armature.find_meshes_affected_by_armature_modifier import find_meshes_affected_by_armature_modifier
from ..armature.normalize_armature_pose import normalize_armature_pose
from ..armature.normalize_armature_rename_bones import normalize_armature_rename_bones
from ..armature.normalize_armature_roll_bones import normalize_armature_roll_bones
from ..bone_desc_map import BONE_DESC_MAP


def perform_normalize_armature(which_pose, apply_rest_pose=True):
    if not which_pose in ["a-pose", "t-pose"]:
        raise Exception("which_pose must be a-pose or t-pose")

    armature = bpy.context.active_object

    if armature == None:
        raise Exception("Please select an armature object first! Got: None")

    if armature.type != "ARMATURE":
        raise Exception(
            "Please select an armature object first! Got: " + armature.type)

    wm = bpy.context.window_manager

    # Progress count, total
    progress = [0]
    progress_total = 0

    def callback_progress_tick():
        progress[0] = progress[0] + 1
        wm.progress_update(progress[0] / progress_total * 100)

    # Progress Total: Rename bones is the length of the bone descriptors
    progress_total += len(BONE_DESC_MAP)

    # Progress Total: T-Pose is:
    # - Fixed count of callback_progress_tick() in the function
    # - Total number of affected meshes
    # - Total number of shape keys in affected meshes
    progress_total += 36
    if apply_rest_pose:
        # Only during apply mode
        affected_meshes = find_meshes_affected_by_armature_modifier(
            armature)
        progress_total += len(affected_meshes)
        for mesh, modifier in affected_meshes:
            if mesh.data.shape_keys != None:
                progress_total += len(mesh.data.shape_keys.key_blocks)

    ######################
    ##  Begin progress  ##

    wm.progress_begin(0, 100)

    # Rename bones
    normalize_armature_rename_bones(armature, callback_progress_tick)

    # Set T-Pose
    normalize_armature_pose(armature, which_pose,
                            apply_rest_pose, callback_progress_tick)

    # Set roll (not worth progress tracking)
    normalize_armature_roll_bones(armature, which_pose)

    wm.progress_end()

    print("Done!")
