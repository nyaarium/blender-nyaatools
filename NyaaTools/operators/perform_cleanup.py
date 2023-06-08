import bpy

from ..mesh.remove_unused_materials import remove_unused_materials
from ..mesh.remove_unused_shape_keys import remove_unused_shape_keys
from ..mesh.remove_unused_vertex_groups import remove_unused_vertex_groups


def perform_cleanup(vg, sk, mat):
    meshes = bpy.context.selected_objects

    if len(meshes) == 0:
        raise Exception("Please select at least 1 mesh object!")

    bpy.ops.object.mode_set(mode="OBJECT")

    for mesh in meshes:
        if vg:
            remove_unused_vertex_groups(mesh)
        if sk:
            remove_unused_shape_keys(mesh)
        if mat:
            remove_unused_materials(mesh)
