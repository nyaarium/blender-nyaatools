import bpy


def selection_add(obj, state=True):
    for col in obj.users_collection:
        col.hide_viewport = False
    obj.hide_set(False)
    obj.select_set(state)
    bpy.context.view_layer.objects.active = obj
