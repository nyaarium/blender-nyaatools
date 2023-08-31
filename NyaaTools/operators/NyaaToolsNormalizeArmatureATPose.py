import traceback
import bpy
from bpy.props import BoolProperty, StringProperty


from ..armature.estimate_is_normalized import estimate_is_normalized
from ..armature.find_meshes_affected_by_armature_modifier import (
    find_meshes_affected_by_armature_modifier,
)
from ..armature.normalize_armature_pose import normalize_armature_pose
from ..armature.normalize_armature_rename_bones import normalize_armature_rename_bones
from ..armature.normalize_armature_roll_bones import normalize_armature_roll_bones
from ..common.selection_get_armature import selection_get_armature
from ..bone_desc_map import BONE_DESC_MAP


class NyaaToolsNormalizeArmatureATPose(bpy.types.Operator):
    """Normalizes armatures to my preferred A or T pose layout"""

    bl_idname = "nyaa.normalize_armature_at_pose"
    bl_label = "Enforce Pose"
    bl_options = {"REGISTER", "UNDO"}

    which_pose: StringProperty(name="Which Pose", default="")
    apply_pose: BoolProperty(name="Apply Pose", default=True)

    apply_roll: BoolProperty(
        name="Roll Bones",
        description="Roll bones such that rotation on local X rotates along the joint. Suitable for posing and animating in Blender. Not so suitable for game character mods.",
        default=True,
    )

    def execute(self, context):
        try:
            armature = selection_get_armature()

            if self.apply_pose:
                perform_normalize_armature(armature, self.which_pose, self.apply_roll)
            else:
                perform_fast_pose(armature, self.which_pose)
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_normalize_armature(armature, which_pose, apply_roll=False):
    if armature == None or armature.type != "ARMATURE":
        raise Exception("Expected an armature")

    if not which_pose in {"a-pose", "t-pose"}:
        raise Exception("which_pose must be a-pose or t-pose")

    if not isinstance(apply_roll, bool):
        raise Exception("apply_roll must be a boolean")

    wm = bpy.context.window_manager

    # Progress count, total
    progress = [0]
    progress_total = 0

    def callback_progress_tick():
        progress[0] = progress[0] + 1
        wm.progress_update(progress[0] / progress_total * 100)

    # Progress Total: T-Pose is:
    # - Fixed count of callback_progress_tick() in the function
    # - Total number of affected meshes
    # - Total number of shape keys in affected meshes
    progress_total += 36
    total_shapekeys = 0

    affected_meshes = find_meshes_affected_by_armature_modifier(armature)
    progress_total += 2 * len(affected_meshes)
    for mesh, modifier in affected_meshes:
        if mesh.data.shape_keys != None:
            total_shapekeys += len(mesh.data.shape_keys.key_blocks)

    progress_total += total_shapekeys

    ######################
    ##  Begin progress  ##

    # Make armature active
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = armature

    wm.progress_begin(0, 100)

    # Rename bones
    normalize_armature_rename_bones(armature)

    # Set T-Pose
    normalize_armature_pose(armature, which_pose, True, callback_progress_tick)

    # Set roll
    normalize_armature_roll_bones(armature, which_pose, apply_roll)

    bpy.ops.object.mode_set(mode="OBJECT")

    wm.progress_end()

    print("Done!")


def perform_fast_pose(armature, which_pose):
    if armature == None or armature.type != "ARMATURE":
        raise Exception("Expected an armature")

    if not which_pose in {"a-pose", "t-pose"}:
        raise Exception("which_pose must be a-pose or t-pose")

    wm = bpy.context.window_manager

    # Progress count, total
    progress = [0]
    progress_total = 0

    def callback_progress_tick():
        progress[0] = progress[0] + 1
        wm.progress_update(progress[0] / progress_total * 100)

    # Progress Total: Rename bones is the length of the bone descriptors
    progress_total += len(BONE_DESC_MAP)

    ######################
    ##  Begin progress  ##

    # Make armature active
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = armature

    if estimate_is_normalized(armature):
        wm.progress_begin(0, 100)

        normalize_armature_pose(armature, which_pose, False, callback_progress_tick)

        bpy.ops.object.mode_set(mode="OBJECT")

        wm.progress_end()
    else:
        raise Exception("Armature is not Nyaa-normalized! Please normalize first.")
