
import re


def remove_unused_vertex_groups(obj):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    if obj.type == None:
        raise BaseException("Expected a mesh object, got: None")
    if obj.type != "MESH":
        raise BaseException("Expected a mesh object, got: " + obj.type)

    obj.update_from_editmode()

    for i, v in sorted(obj.vertex_groups.items(), reverse=True):
        if (v.name.startswith("--")):
            obj.vertex_groups.remove(obj.vertex_groups[i])

    vgroup_used = {i: False for i, k in enumerate(obj.vertex_groups)}
    vgroup_names = {i: k.name for i, k in enumerate(obj.vertex_groups)}

    for v in obj.data.vertices:
        for g in v.groups:
            if g.weight > 0.0:
                vgroup_used[g.group] = True
                vgroup_name = vgroup_names[g.group]
                armatch = re.search(
                    '((.R|.L)(.(\d){1,}){0,1})(?!.)', vgroup_name)
                if armatch != None:
                    tag = armatch.group()
                    mirror_tag = tag.replace(".R", ".L") if armatch.group(
                        2) == ".R" else tag.replace(".L", ".R")
                    mirror_vgname = vgroup_name.replace(tag, mirror_tag)
                    for i, name in sorted(vgroup_names.items(), reverse=True):
                        if mirror_vgname == name:
                            vgroup_used[i] = True
                            break

    for i, used in sorted(vgroup_used.items(), reverse=True):
        if not used:
            debug_print("Removing vertex group: ",
                        obj.name, " -> ", vgroup_names[i])
            obj.vertex_groups.remove(obj.vertex_groups[i])
