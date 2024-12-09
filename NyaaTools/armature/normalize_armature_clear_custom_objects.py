import bpy

def normalize_armature_clear_custom_objects(armature: bpy.types.Armature):
    def debug_print(*msgs):
        print("   ", *msgs)
        return


    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = armature

    # Switch to pose mode
    bpy.ops.object.mode_set(mode="POSE")

    # Iterate over all pose bones and clear custom shapes
    for pose_bone in armature.pose.bones:
        if pose_bone.custom_shape is not None:
            debug_print("Clearing custom shape of", pose_bone.name)
            pose_bone.custom_shape = None

    # Switch back to object mode
    bpy.ops.object.mode_set(mode="OBJECT")
