from .remove_unused_vertex_groups import remove_unused_vertex_groups
from .remove_unused_shape_keys import remove_unused_shape_keys
from .remove_unused_materials import remove_unused_materials


def cleanup_mesh(obj):
    if obj == None:
        raise BaseException("cleanupMesh() :: Expected a mesh object, got: None")
    if obj.type != "MESH":
        raise BaseException("cleanupMesh() :: Expected a mesh object")

    remove_unused_vertex_groups(obj)
    remove_unused_shape_keys(obj)
    remove_unused_materials(obj)
