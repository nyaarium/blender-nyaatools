import bpy


def selection_get_armature():
    armature = None

    selected_armatures = []
    for obj in bpy.context.selected_objects:
        if obj.type == "ARMATURE":
            selected_armatures.append(obj)

            if len(selected_armatures) == 1:
                armature = obj
            else:
                armature = None
                break

    return armature
