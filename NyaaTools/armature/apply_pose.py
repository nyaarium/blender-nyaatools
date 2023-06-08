
import bpy

from .._external.przemir.helper import applyModifierForObjectWithShapeKeys


def apply_pose(armature, mesh_modifier_pairs, callback_progress_tick=None):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="DESELECT")

    for mesh, modifier in mesh_modifier_pairs:
        if callback_progress_tick != None:
            if callback_progress_tick != None:
                callback_progress_tick()

        # Select the mesh
        mesh.select_set(True)
        bpy.context.view_layer.objects.active = mesh

        debug_print("Applying pose to mesh ", mesh.name, modifier.name)
        # Duplicate modifier & apply it
        modifier_copy = mesh.modifiers.new(modifier.name, modifier.type)
        debug_print("Copied modifier", modifier_copy.name)
        modifier_copy.object = modifier.object
        modifier_copy.use_deform_preserve_volume = True

        # If shape keys exist (note that shape_keys may be None)
        if mesh.data.shape_keys != None:
            applyModifierForObjectWithShapeKeys(
                bpy.context,
                [modifier_copy.name],
                True,
                callback_progress_tick
            )

        else:
            bpy.ops.object.modifier_apply(modifier=modifier_copy.name)

        # Unselect
        mesh.select_set(False)
        bpy.context.view_layer.objects.active = None

    # Select the armature
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

    # Set pose as rest pose
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply()
