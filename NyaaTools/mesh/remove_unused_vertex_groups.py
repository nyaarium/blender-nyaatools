import re

from ..consts import VERTEX_GROUP_TOLERANCE


def remove_unused_vertex_groups(obj):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    if obj.type == None:
        raise BaseException("Expected a mesh object, got: None")
    if obj.type != "MESH":
        raise BaseException("Expected a mesh object, got: " + obj.type)

    obj.update_from_editmode()

    # Dictionary to track usage of vertex groups
    vgroup_used = {i: False for i, vg in enumerate(obj.vertex_groups)}
    vgroup_names = {i: vg.name for i, vg in enumerate(obj.vertex_groups)}

    # Determine usage of vertex groups
    for v in obj.data.vertices:
        for g in v.groups:
            if VERTEX_GROUP_TOLERANCE < g.weight:
                vgroup_used[g.group] = True
                # Mirror vertex group handling
                armatch = re.search(
                    r"((.R|.L)(.(\d){1,}){0,1})(?!.)", vgroup_names[g.group]
                )
                if armatch:
                    tag = armatch.group()
                    mirror_tag = (
                        tag.replace(".R", ".L")
                        if ".R" in tag
                        else tag.replace(".L", ".R")
                    )
                    mirror_vgname = vgroup_names[g.group].replace(tag, mirror_tag)
                    # Ensure mirror group is marked used
                    for idx, name in vgroup_names.items():
                        if mirror_vgname == name:
                            vgroup_used[idx] = True
                            break

    # Remove unused vertex groups by iterating over indices in reverse order
    for idx in sorted(vgroup_used.keys(), reverse=True):
        if not vgroup_used[idx]:
            print(f"Removing vertex group:  {obj.name} -> {vgroup_names[idx]}")
            obj.vertex_groups.remove(obj.vertex_groups[idx])
