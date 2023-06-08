import bpy

from ..armature.find_bone import find_bone
from ..bone_desc_map import BONE_DESC_MAP


def estimate_is_normalized(armature: bpy.types.Armature):
    # Iterate over descriptors in BONE_DESC_MAP & rename if not the desired name
    for bone_desc_name in BONE_DESC_MAP:
        bone_desc = BONE_DESC_MAP[bone_desc_name]

        if bone_desc_name.startswith("Hand"):
            # This is good enough of an estimate.
            return True

        bone = find_bone("edit", armature, bone_desc_name)
        if bone == None:
            return False

        if bone.name != bone_desc_name:
            return False

        if bone.name == bone_desc_name:
            # Check if bone is connected
            if "connected" in bone_desc and bone_desc["connected"]:
                if not bone.use_connect:
                    return False
            else:
                if bone.use_connect:
                    return False

    # All are good
    return True
