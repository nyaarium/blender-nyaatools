import bpy


def selection_get_meshes():
    selected_meshes = []
    for obj in bpy.context.selected_objects:
        if obj.type == "MESH":
            selected_meshes.append(obj)

    return selected_meshes
