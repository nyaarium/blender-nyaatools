def clear_pose(armature):
    for bone in armature.pose.bones:
        bone.matrix_basis.identity()
