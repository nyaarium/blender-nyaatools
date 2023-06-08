import bpy

from .._external.przemir.helper import applyModifierForObjectWithShapeKeys


def perform_apply_top_modifier():
    meshes = bpy.context.selected_objects

    if len(meshes) == 0:
        raise Exception("Please select at least 1 mesh object!")

    bpy.ops.object.mode_set(mode="OBJECT")

    for mesh in meshes:
        if mesh.type != "MESH":
            continue

        if 0 < len(mesh.modifiers):
            mesh.select_set(True)

            modifier = mesh.modifiers[0]

            applyModifierForObjectWithShapeKeys(
                bpy.context,
                [modifier.name],
                True
                # callback_progress_tick
            )
