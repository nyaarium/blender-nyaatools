import traceback
import bpy


class NyaaToolsDissolveBones(bpy.types.Operator):
    """Dissolve a selection of bones and combine the vertex groups of affected meshes. Good for reducing hair bones. Important: Only affects meshes that have this armature as the deform modifier."""

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


def perform_dissolve_bones():
    obj = bpy.context.view_layer.objects.active
    if obj == None or obj.type != "ARMATURE":
        raise Exception("Expected an armature")

    if bpy.context.mode != "EDIT_ARMATURE":
        raise Exception("Must be in edit mode of an armature")

    def find_starting_point(selected_bones, bone):
        # If the bone has a parent and the parent is not in the selected bones,
        # return the parent
        if bone.parent and bone.parent not in selected_bones:
            return bone.parent
        # If the bone has a parent that is in the selected bones,
        # recursively find the starting point
        elif bone.parent:
            return find_starting_point(selected_bones, bone.parent)
        # If the bone has no parent or its parent is not in the selected bones,
        # it is the starting point
        else:
            return bone

    # Step 1: Loop over all mesh objects and include if it is affected by armature.
    meshes_affected_by_armature = []
    for mesh in bpy.data.objects:
        if mesh.type == "MESH":
            for mod in mesh.modifiers:
                if mod.type == "ARMATURE":
                    meshes_affected_by_armature.append(mesh)

    # Step 2: Get selection of bones from current selection
    selected_bones = bpy.context.selected_bones
    print("Selected bones:", selected_bones)

    # Step 3: Loop over selected bones and make them connected if their parent is also selected
    for bone in selected_bones:
        if bone.parent in selected_bones:
            bone.use_connect = True

    # Step 4: Loop over meshes and combine the affected vertex group weights.
    for mesh in meshes_affected_by_armature:
        for bone in selected_bones:
            starting_bone = find_starting_point(selected_bones, bone)
            print("Starting bone:", starting_bone.name, "  Bone:", bone.name)

            # Get the vertex group for the bone
            vg = mesh.vertex_groups.get(bone.name)

            # If the vertex group exists
            if vg:
                # Get the vertex group for the starting bone
                starting_vg = mesh.vertex_groups.get(starting_bone.name)

                # If the starting vertex group doesn't exist, create it
                if not starting_vg:
                    starting_vg = mesh.vertex_groups.new(name=starting_bone.name)

                # Loop over the vertices in the vertex group
                for vert in mesh.data.vertices:
                    # Try to get the weight of the vertex for the current bone
                    try:
                        weight = vg.weight(vert.index)

                        # Add the weight to the starting bone's vertex group
                        starting_vg.add([vert.index], weight, "ADD")
                    except RuntimeError:
                        continue

                # Remove the current bone's vertex group
                mesh.vertex_groups.remove(vg)
                print("Removed vertex group:", bone.name)

    # Step 5: Dissolve bone selection.
    bpy.ops.armature.dissolve()
