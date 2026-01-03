import math
import bpy

from ..bone_desc_map import BONE_DESC_MAP


def normalize_armature_retarget(armature, source_armature, animation_name: str):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    if armature is None or armature.type != "ARMATURE":
        raise Exception("Expected a target armature")

    if source_armature is None or source_armature.type != "ARMATURE":
        raise Exception("Expected a source armature")

    debug_print("Animation:", animation_name)

    # Switch to pose mode
    bpy.ops.object.mode_set(mode="POSE")

    for bone_desc_name in BONE_DESC_MAP:
        if bone_desc_name in armature.pose.bones:
            target_bone = armature.pose.bones[bone_desc_name]

            debug_print("Processing bone:", target_bone.name)

            # - Delete any existing "Copy Transforms" constraint
            # - Create a new "Copy Transforms" constraint and set:
            #     Target = source
            #     Bone = the matching bone name on source
            #     Orientation Target: Local Space (Owner Orientation)
            #     Orientation Owner:  Local Space
