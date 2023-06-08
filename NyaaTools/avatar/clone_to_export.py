import bpy

from ..consts import EXPORT_COLLECTION


def clone_to_export(obj):
    if (obj == None):
        raise BaseException(
            "cloneToExport() :: Expected a mesh object, got: None")

    copied = obj.copy()
    if (obj.type == "MESH"):
        copied.data = copied.data.copy()
    bpy.data.collections[EXPORT_COLLECTION].objects.link(copied)
    return copied
