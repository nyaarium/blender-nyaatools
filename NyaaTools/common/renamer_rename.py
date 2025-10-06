import bpy


def rename_object(obj, new_name):
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


def rename_material(material, new_name):
    """Rename a material and handle conflicts, returning unrename info."""
    unrename_info = []
    
    if new_name in bpy.data.materials:
        if material == bpy.data.materials[new_name]:
            # This material is itself, skip renaming
            pass
        else:
            # There is a conflict, rename the original material and supply an unrename
            conflict_material = bpy.data.materials[new_name]
            temp_name = "____" + conflict_material.name
            unrename_info.append(("material", temp_name, conflict_material.name))
            conflict_material.name = temp_name
            material.name = new_name
    else:
        # No conflict, rename material
        material.name = new_name
    
    return unrename_info
