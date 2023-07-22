import bpy

from ..armature.find_bone import find_bone
from ..bone_desc_map import BONE_DESC_MAP


def normalize_armature_rename_bones(armature: bpy.types.Armature):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    def perform_rename(bone_desc_name, bone):
        if bone.name == bone_desc_name:
            debug_print("Name is good: ", bone.name)
        else:
            debug_print("Renaming: ", bone.name, " to ", bone_desc_name)
            bone.name = bone_desc_name

    debug_print("Starting normalize_armature_rename_bones()")

    # Iterate over descriptors in BONE_DESC_MAP & rename if not the desired name
    # Breast bones are handled separately
    for bone_desc_name in BONE_DESC_MAP:
        bone_desc = BONE_DESC_MAP[bone_desc_name]

        if bone_desc_name.startswith("Breast"):
            continue

        bone = find_bone("edit", armature, bone_desc_name)
        if bone == None:
            if "optional" in bone_desc and bone_desc["optional"]:
                continue
            else:
                raise TypeError("Couldn't find bone: " + bone_desc_name)

        perform_rename(bone_desc_name, bone)

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

    # Handle breast bones
    using_breast_bones = (
        find_bone("edit", armature, "Breast Root") != None
        or find_bone("edit", armature, "Breast.L") != None
        or find_bone("edit", armature, "Breast.R") != None
        or find_bone("edit", armature, "Breast.L", "Chest") != None
        or find_bone("edit", armature, "Breast.R", "Chest") != None
    )
    if using_breast_bones:
        breastRoot = find_bone("edit", armature, "Breast Root")
        if breastRoot != None:
            # Root already exists, just rename it
            if breastRoot.name == "Breast Root":
                debug_print("Name is good: ", breastRoot.name)
            else:
                debug_print("Renaming: ", breastRoot.name, " to ", "Breast Root")
                breastRoot.name = "Breast Root"
        else:
            # No root bone, but there are breast bones, create a new root
            breastL = find_bone("edit", armature, "Breast.L", "Chest")
            breastR = find_bone("edit", armature, "Breast.R", "Chest")

            if breastL != None and breastR != None:
                new_z = breastL.head.z

                breastRoot = armature.data.edit_bones.new("Breast Root")
                breastRoot.head = (0, -0.02, new_z)
                breastRoot.tail = (0, -0.02, new_z + 0.05)
                breastRoot.parent = find_bone("edit", armature, "Chest")
                breastL.parent = breastRoot
                breastR.parent = breastRoot

                debug_print("Created new bone: Breast Root")

        breastL = find_bone("edit", armature, "Breast.L")
        perform_rename("Breast.L", breastL)

        breastR = find_bone("edit", armature, "Breast.R")
        perform_rename("Breast.R", breastR)
