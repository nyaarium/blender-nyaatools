import traceback
import bpy
from bpy.props import BoolProperty

from .perform_cleanup import perform_cleanup


class NyaaToolsMeshCleanup(bpy.types.Operator):
    """Removes unused vertex groups, shape keys, and materials from a mesh object"""
    bl_idname = "nyaa.mesh_cleanup"
    bl_label = "Mesh Cleanup"
    bl_options = {"REGISTER", "UNDO"}

    vg: BoolProperty(name="Vertex Groups", default=False)
    sk: BoolProperty(name="Shape Keys", default=False)
    mat: BoolProperty(name="Materials", default=False)

    def execute(self, context):
        try:
            perform_cleanup(self.vg, self.sk, self.mat)
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
