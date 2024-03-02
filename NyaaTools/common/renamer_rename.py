import bpy


def renamer_rename(obj, new_name):
    def get_obj_data(obj):
        if obj.type == "MESH":
            return bpy.data.meshes
        elif obj.type == "ARMATURE":
            return bpy.data.armatures
        else:
            return None

    unrename_info = []

    if new_name in bpy.data.objects:
        if obj == bpy.data.objects[new_name]:
            # This object is itself, skip renaming
            pass
        else:
            # There is a conflict, rename the original object and supply an unrename
            conflict_obj = bpy.data.objects[new_name]
            temp_name = "____" + conflict_obj.name
            unrename_info.append(("object", temp_name, conflict_obj.name))
            conflict_obj.name = temp_name
            obj.name = new_name
    else:
        # No conflict, rename object
        obj.name = new_name

    # Sometimes selected objects dont have data, like a light probe. Check for None
    data_col = get_obj_data(obj)
    if data_col:
        if new_name in data_col:
            if obj.data == data_col[new_name]:
                # This data is itself, skip renaming
                pass
            else:
                # There is a conflict, rename the original data and supply an unrename
                conflict_data = data_col[new_name]
                temp_name = "____" + conflict_data.name
                unrename_info.append((obj.type.lower(), temp_name, conflict_data.name))
                conflict_data.name = temp_name
                obj.data.name = new_name
        else:
            # No conflict, rename data
            obj.data.name = new_name

    return unrename_info
