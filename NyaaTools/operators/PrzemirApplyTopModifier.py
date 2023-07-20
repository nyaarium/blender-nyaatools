import traceback
import bpy

from ..common.deselect_all import deselect_all
from ..common.selection_get_meshes import selection_get_meshes
from .._external.przemir.helper import applyModifierForObjectWithShapeKeys


class PrzemirApplyTopModifier(bpy.types.Operator):
    """Apply the topmost modifier for object with shape keys (GitHub/przemir)"""

    bl_idname = "przemir.apply_top_modifier"
    bl_label = "Add Modifier"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            meshes = selection_get_meshes()

            perform_apply_top_modifier(meshes)
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_apply_top_modifier(meshes):
    if not isinstance(meshes, list) or len(meshes) == 0:
        raise Exception("Please select at least 1 mesh object!")

    wm = bpy.context.window_manager

    # Progress count, total
    progress = [0]
    progress_total = 0

    def callback_progress_tick():
        progress[0] = progress[0] + 1
        wm.progress_update(progress[0] / progress_total * 100)

    # Progress Total: Shape key apply is:
    # - Total number meshes
    # - Total number of shape keys in all meshes
    progress_total += len(meshes)
    for mesh in meshes:
        if mesh.data.shape_keys != None:
            progress_total += len(mesh.data.shape_keys.key_blocks)

    ######################
    ##  Begin progress  ##

    bpy.ops.object.mode_set(mode="OBJECT")

    wm.progress_begin(0, 100)

    for mesh in meshes:
        if 0 < len(mesh.modifiers):
            bpy.context.view_layer.objects.active = mesh

            modifier = mesh.modifiers[0]

            applyModifierForObjectWithShapeKeys(
                bpy.context,
                [modifier.name],
                True,
                callback_progress_tick,
            )

    wm.progress_end()
