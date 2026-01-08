import traceback
import bpy
from bpy.props import BoolProperty

from ..common.selection_get_meshes import selection_get_meshes
from ..mesh.remove_unused_materials import remove_unused_materials
from ..mesh.remove_unused_shape_keys import remove_unused_shape_keys
from ..mesh.remove_unused_vertex_groups import remove_unused_vertex_groups
from ..asset.merge_layers import sort_mesh_elements_by_material


class NYAATOOLS_OT_MeshCleanup(bpy.types.Operator):
    """Removes unused vertex groups, shape keys, and materials from a mesh object"""

    bl_idname = "nyaa.mesh_cleanup"
    bl_label = "Mesh Cleanup"
    bl_options = {"REGISTER", "UNDO"}

    vg: BoolProperty(name="Vertex Groups", default=False)
    sk: BoolProperty(name="Shape Keys", default=False)
    mat: BoolProperty(name="Materials", default=False)

    def execute(self, context):
        try:
            meshes = selection_get_meshes()

            perform_cleanup(meshes, self.vg, self.sk, self.mat)
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_cleanup(meshes, vg, sk, mat):
    if not isinstance(meshes, list) or len(meshes) == 0:
        raise Exception("Please select at least 1 mesh object!")

    bpy.ops.object.mode_set(mode="OBJECT")

    for mesh in meshes:
        if vg:
            remove_unused_vertex_groups(mesh)
        if sk:
            remove_unused_shape_keys(mesh)
        if mat:
            remove_unused_materials(mesh)

            # Sort mesh elements by material for better game engine compatibility
            sort_mesh_elements_by_material(mesh)
