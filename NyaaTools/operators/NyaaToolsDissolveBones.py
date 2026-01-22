import traceback
import bpy

from ..asset.asset_lookup import get_asset_meshes_by_layer


class NYAATOOLS_OT_DissolveBones(bpy.types.Operator):
    """Dissolve a selection of bones and combine the vertex groups. Affects meshes from the Asset's layer config (if asset) plus any other meshes using this armature modifier."""

    bl_idname = "nyaa.dissolve_bones"
    bl_label = "Dissolve Bones"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            perform_dissolve_bones()

            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def contiguous_check(selected_bones):
    selected_set = set(selected_bones)

    top_parent = None
    leaf_bone = None  # Track the leaf-most bone
    orphans = []

    # Find the top-most parent in the selection
    for bone in selected_bones:
        if bone.parent not in selected_set:
            if top_parent is not None:
                raise Exception(
                    "Multiple top-most parents found. Make sure your selection is contiguous."
                )
            top_parent = bone

    if top_parent is None:
        raise Exception(
            "No top-most parent found. Make sure your selection is contiguous."
        )

    # Traverse from the top_parent down, ensuring all selected bones are connected, and determine orphans
    def recurse(bone, visited):
        nonlocal leaf_bone
        visited.add(bone)
        # Collect orphans from children of the current bone if it's not the top_parent
        if bone != top_parent:
            for child in bone.children:
                if child not in selected_set:
                    orphans.append(child)
        # Continue traversing the selected bones
        leaf_bone = bone  # Update the leaf-most bone at each step
        for child in bone.children:
            if child in selected_set and child not in visited:
                recurse(child, visited)

    visited = set()
    recurse(top_parent, visited)

    if visited != selected_set:
        raise Exception(
            "Not all selected bones are in the same chain. Make sure your selection is contiguous."
        )

    if leaf_bone is None:
        raise Exception(
            "No leaf-most bone found. Make sure your selection is contiguous."
        )

    # Get the tail position of the leaf-most bone
    tail_position = leaf_bone.tail

    return top_parent, orphans, tail_position


def perform_dissolve_bones():
    obj = bpy.context.view_layer.objects.active
    if obj == None or obj.type != "ARMATURE":
        raise Exception("Expected an armature")

    if bpy.context.mode != "EDIT_ARMATURE":
        raise Exception("Must be in edit mode of an armature")

    # Store original state
    original_x_mirror = obj.data.use_mirror_x

    # Disable X mirror temporarily
    obj.data.use_mirror_x = False

    selected_bones = bpy.context.selected_editable_bones
    selected_bones_names = [bone.name for bone in selected_bones]
    if len(selected_bones) < 2:
        raise Exception("At least two bones must be selected")

    # Step 1: Verify selection of bones
    top_parent, orphans, tail_position = contiguous_check(selected_bones)
    print("Selected bones:", selected_bones_names)
    print("Top parent:", top_parent.name)
    print("Orphans:", [bone.name for bone in orphans])
    print("Tail position:", tail_position)

    # Step 2: Make selected bones connected if their parent is also selected
    for bone in selected_bones:
        if bone.parent and bone.parent in selected_bones:
            bone.use_connect = True

    # Step 3: Collect meshes from both Asset layers and armature modifier references.
    # This ensures we affect: (1) All meshes in the Asset's layer config, and
    # (2) Any non-tracked meshes that happen to use this armature.
    meshes_affected = set()

    # Source 1: Asset system layers (if this armature is an asset)
    if hasattr(obj, "nyaa_asset") and obj.nyaa_asset.is_asset:
        layer_dict = get_asset_meshes_by_layer(obj)
        for layer_meshes in layer_dict.values():
            for mesh in layer_meshes.values():
                meshes_affected.add(mesh)

    # Source 2: Any mesh with an armature modifier pointing to this armature
    for mesh in bpy.data.objects:
        if mesh.type == "MESH":
            for mod in mesh.modifiers:
                if mod.type == "ARMATURE" and mod.object == obj:
                    meshes_affected.add(mesh)
                    break

    # Step 4: Loop over meshes and combine the affected vertex group weights.
    for mesh in meshes_affected:
        vg_names_to_remove = []

        for bone in selected_bones:
            # Get the vertex group for the bone (skip if not found)
            vg = mesh.vertex_groups.get(bone.name)
            if vg:
                if bone != top_parent:
                    vg_names_to_remove.append(bone.name)

                # Get the vertex group for the top bone (create if not found)
                top_vg = mesh.vertex_groups.get(top_parent.name)
                if not top_vg:
                    top_vg = mesh.vertex_groups.new(name=top_parent.name)

                # Loop over the vertices in the vertex group
                for vert in mesh.data.vertices:
                    try:
                        weight = vg.weight(vert.index)

                        # Add the weight to the top bone's vertex group
                        top_vg.add([vert.index], weight, "ADD")
                    except RuntimeError:
                        continue

        for vg_name in vg_names_to_remove:
            vg = mesh.vertex_groups.get(vg_name)
            mesh.vertex_groups.remove(vg)
            print("Removed vertex group:", mesh.name, ">", vg_name)

    # Step 5: Reparent orphans to the top parent and move tail
    for orphan in orphans:
        orphan.parent = top_parent
        if orphan.head == top_parent.tail:
            orphan.use_connect = True
    top_parent.tail = tail_position

    # Step 6: Delete non-top bones (last because cache destructive)
    bpy.ops.armature.select_all(action="DESELECT")
    for bone in selected_bones:
        if bone != top_parent:
            bone.select = True
    bpy.ops.armature.delete(confirm=False)

    # Restore original state after all operations are complete
    obj.data.use_mirror_x = original_x_mirror
