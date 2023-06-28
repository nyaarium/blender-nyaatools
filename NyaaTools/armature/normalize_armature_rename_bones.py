import bpy

from ..armature.find_bone import find_bone
from ..bone_desc_map import BONE_DESC_MAP


def normalize_armature_rename_bones(armature: bpy.types.Armature):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    debug_print("Starting normalize_armature_rename_bones()")

    # Iterate over descriptors in BONE_DESC_MAP & rename if not the desired name
    for bone_desc_name in BONE_DESC_MAP:
        bone_desc = BONE_DESC_MAP[bone_desc_name]

        bone = find_bone("edit", armature, bone_desc_name)
        if bone == None:
            if "optional" in bone_desc and bone_desc["optional"]:
                continue
            else:
                raise TypeError("Couldn't find bone: " + bone_desc_name)

        if bone.name == bone_desc_name:
            debug_print("Name is good: ", bone.name)

        # Do rename
        if bone.name != bone_desc_name:
            debug_print("Renaming: ", bone.name, " to ", bone_desc_name)
            bone.name = bone_desc_name

        # Check if bone is connected
        if "connected" in bone_desc and bone_desc["connected"]:
            if not bone.use_connect:
                debug_print("Connecting bone: ", bone.name)

                # Move parent's tail to this head
                bone.parent.tail = bone.head

                bone.use_connect = True
        else:
            if bone.use_connect:
                debug_print("Detaching bone: ", bone.name)

                bone.use_connect = False
