import bpy


def list_bone_merge_conflicts(target_armature, extra_armature):
    """
    List name of bone merge conflicts between two armatures.
    """
    conflicts = []
    for bone in target_armature.data.bones:
        if bone.name in extra_armature.data.bones:
            conflicts.append(bone.name)
    return conflicts
