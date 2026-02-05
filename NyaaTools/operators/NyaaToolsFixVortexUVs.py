"""
Fast Unwrap Mesh Operator.

Quickly unwraps a mesh by detecting and repairing distorted UV islands
through automated seam placement. Trade quality for speed. Useful for rapid tests.
"""

import traceback
import bpy

from ..common.selection_get_meshes import selection_get_meshes
from ..uv.fix_vortex_uvs import detect_and_fix_vortex_islands


class NYAATOOLS_OT_FixVortexUVs(bpy.types.Operator):
    """Fast unwrap with aggressive seam placement to fix distorted islands."""

    bl_idname = "nyaa.fix_vortex_uvs"
    bl_label = "Fast Unwrap Mesh"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            return False
        if len(obj.data.uv_layers) == 0:
            return False
        return True

    def execute(self, context):
        try:
            mesh_obj = context.active_object

            if mesh_obj is None or mesh_obj.type != "MESH":
                self.report({"ERROR"}, "Please select a mesh object")
                return {"CANCELLED"}

            if len(mesh_obj.data.uv_layers) == 0:
                self.report({"ERROR"}, "Mesh has no UV layers")
                return {"CANCELLED"}

            # Use active UV layer
            uv_layer_index = mesh_obj.data.uv_layers.active_index

            # Ensure we're in object mode
            if mesh_obj.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            # Run vortex fix
            stats = detect_and_fix_vortex_islands(
                context, mesh_obj, uv_layer_index, restore_seams=False
            )

            # Report results
            msg = (
                f"Checked {stats['islands_checked']} islands, "
                f"found {stats['vortexes_found']} vortexes, "
                f"fixed {stats['vortexes_fixed']}"
            )
            self.report({"INFO"}, msg)

            # Report per-island metrics
            metrics = stats.get("island_metrics", [])
            for i, m in enumerate(metrics):
                dr = m.get("density_ratio", 0)
                cv = m.get("max_shape_cv", 0)
                iv = m.get("is_vortex", False)
                self.report(
                    {"INFO"},
                    f"Island {i}: density_ratio={dr:.2f}, shape_cv={cv:.3f}, is_vortex={iv}",
                )

            return {"FINISHED"}

        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
