import bpy

from .similarity_to_common_names import similarity_to_common_names
from ..bone_desc_map import BONE_DESC_MAP


# returns bone or None that is most likely to be the bone_desc_name described in bones_map
def find_bone(
    which, armature: bpy.types.Armature, bone_desc_name: str
) -> bpy.types.EditBone:
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    if which not in ["edit", "pose"]:
        raise TypeError("which must be either 'edit' or 'pose'")

    if not isinstance(bone_desc_name, str):
        raise TypeError("bone_desc_name must be type str")

    # If bone_name not in bones_map, throw exception
    if bone_desc_name not in BONE_DESC_MAP:
        raise TypeError(
            "["
            + bone_desc_name
            + "] not in bones_map! Expected an exact name of a Bone Descriptor."
        )

    def probability_parent(bone_desc_name, bone, stop_counter=0):
        def debug_print(*msgs):
            # print("   ", "   ", *msgs)
            return

        if not isinstance(bone_desc_name, str):
            raise TypeError("bone_desc_name must be type str")

        # This check only happens if there is a parent to compare
        if bone.parent and BONE_DESC_MAP[bone_desc_name]["parent"] and stop_counter < 3:
            parent_name = bone.parent.name

            # Parent descriptor
            parent_desc_name = BONE_DESC_MAP[bone_desc_name]["parent"]

            # If exact match, return bone
            if parent_name == parent_desc_name:
                debug_print("* Exact match ", parent_name, " == ", parent_desc_name)
                return 1

            debug_print("Comparing ", parent_name, " to ", parent_desc_name)

            # If the parent is a match, return the bone
            if 0.8 <= similarity_to_common_names(parent_name, parent_desc_name):
                debug_print(bone.name, " seems to be ", bone_desc_name)
                return probability_parent(
                    parent_desc_name, bone.parent, stop_counter + 1
                )
            else:
                debug_print("* Not a match!")
                return 0

        s = similarity_to_common_names(bone.name, bone_desc_name)
        s += 0.1 * stop_counter
        if 0.8 <= s:
            debug_print("* Likely match: ", bone.name, " == ", bone_desc_name)
            return s
        else:
            debug_print("* Not a match!")
            return 0

    def check_child(bone_desc_name, bone):
        def debug_print(*msgs):
            # print("   ", "   ", *msgs)
            return

        if not isinstance(bone_desc_name, str):
            raise TypeError("bone_desc_name must be type str")

        for child_bone in bone.children:
            child_name = child_bone.name

            debug_print("Checking child:", child_name)

            bone_desc = BONE_DESC_MAP[bone_desc_name]

            # Child descriptor
            if bone_desc["children"]:
                for child_desc_name in bone_desc["children"]:
                    debug_print("Comparing it to:", child_desc_name)

                    # If exact match, return bone
                    if child_name == child_desc_name:
                        debug_print(
                            "* Exact match ", child_name, " == ", child_desc_name
                        )
                        return True

                    # If the child is a match, return the bone
                    if 0.8 <= similarity_to_common_names(child_name, child_desc_name):
                        debug_print(
                            "* Child is a good match", bone.name, " is ", bone_desc_name
                        )
                        return True

        return False

    bones = []
    if which == "edit":
        bpy.ops.object.mode_set(mode="EDIT")
        bones = armature.data.edit_bones
    elif which == "pose":
        bpy.ops.object.mode_set(mode="POSE")
        bones = armature.pose.bones

    bone_matches = []

    # All bones in armature that are similar to the common_names
    for bone in bones:
        # If exact match, return bone
        if bone.name == bone_desc_name:
            return bone

        # If exists in BONE_DESC_MAP as a different bone, skip
        if bone.name in BONE_DESC_MAP:
            continue

        if 0.75 <= similarity_to_common_names(bone.name, bone_desc_name):
            bone_matches.append(bone)

    debug_print("Similar names:", [b.name for b in bone_matches])

    if len(bone_matches) == 0:
        return None

    # Loop over bone_matches and store pairs of [likeliness, bone]
    likely_bone = []
    for bone in bone_matches:
        if bone.parent:
            if probability_parent(bone_desc_name, bone):
                likely_bone.append(
                    [similarity_to_common_names(bone.name, bone_desc_name), bone]
                )

    # If a likely one was found, return the max of likely_bone[1]
    if len(likely_bone):
        debug_print("Very likely matches:", [(b[1].name) for b in likely_bone])
        return max(likely_bone, key=lambda b: b[0])[1]

    # Check immediate bones, and if they look like what BONE_DESC_MAP describes, add them to likely_bone
    if bone.children:
        for bone in bone_matches:
            if check_child(bone_desc_name, bone):
                likely_bone.append(
                    [similarity_to_common_names(bone.name, bone_desc_name), bone]
                )

        debug_print("Likely matches:", [(b[1].name) for b in likely_bone])

        # If a likely one was found, return it
        if len(likely_bone):
            debug_print("Very likely matches:", [(b[1].name) for b in likely_bone])
            return max(likely_bone, key=lambda b: b[0])[1]

    return None
