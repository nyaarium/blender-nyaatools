import bpy


def get_top_level_orphan_bones(target_armature, extra_armature, conflicts):
    """
    List name of top-most bone that would be orphaned by a merge.
    """
    target_bone_names = {
        bone.name for bone in target_armature.data.bones
    }  # Names of bones in target armature
    orphaned_bones = []

    for bone in extra_armature.data.bones:
        # Bone is an orphan if it's not in the target and no conflict with its name
        if bone.name not in target_bone_names and bone.name not in conflicts:
            # Walk up the parent chain to determine if this is the top-level orphan
            current_bone = bone
            top_level_orphan = True
            while current_bone.parent is not None:
                if (
                    current_bone.parent.name in target_bone_names
                    or current_bone.parent.name in conflicts
                ):
                    top_level_orphan = False
                    break
                current_bone = current_bone.parent

            # Check if the current bone is the top-level in its chain
            if top_level_orphan and current_bone.name == bone.name:
                orphaned_bones.append(bone.name)

    return orphaned_bones
