import bpy

from ..common.selection_add import selection_add


def remove_unused_materials(obj):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    if obj.type == None:
        raise BaseException("Expected a mesh object, got: None")
    if obj.type != "MESH":
        raise BaseException("Expected a mesh object, got: " + obj.type)

    mat_slots = {}
    for p in obj.data.polygons:
        mat_slots[p.material_index] = 1

    mat_slots = mat_slots.keys()

    for i in reversed(range(len(obj.material_slots))):
        if i not in mat_slots:
            mat_name = obj.material_slots[i].name
            if mat_name != "":
                mat_name = " (" + mat_name + ")"
            debug_print("Removing material slot: ", obj.name, " -> ", i, mat_name)

            selection_add(obj)
            obj.active_material_index = i
            bpy.ops.object.material_slot_remove()
