import traceback
import bpy
from bpy.props import StringProperty

from ..common.selection_get_meshes import selection_get_meshes


class NyaaToolsAddModifier(bpy.types.Operator):
    """Adds a modifier to the selected objects"""

    bl_idname = "nyaa.add_modifier"
    bl_label = "Add Modifier"
    bl_options = {"REGISTER", "UNDO"}

    # Armature
    # DataTransfer
    # Decimate
    which_modifier: StringProperty(name="Which Modifier", default="")

    def execute(self, context):
        try:
            meshes = selection_get_meshes()

            perform_add_modifier(meshes, self.which_modifier)
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_add_modifier(meshes, which_modifier):
    def move_modifier_to_top(modifier):
        for i in range(len(modifier.id_data.modifiers)):
            if modifier == modifier.id_data.modifiers[0]:
                break
            bpy.ops.object.modifier_move_up(modifier=modifier.name)

    def search_for_avatar_armature(mesh):
        """Find the avatar armature that owns this mesh using PropertyGroup system."""
        for obj in bpy.data.objects:
            if obj.type != "ARMATURE" or not obj.nyaa_avatar.is_avatar:
                continue
            for entry in obj.nyaa_avatar.meshes:
                if entry.mesh_object == mesh:
                    return obj
        return None

    # Only returns an armature if there is only 1 armature in the scene
    def search_for_only_armature():
        ret = None
        for obj in bpy.data.objects:
            if obj.type == "ARMATURE":
                if ret != None:
                    return None
                ret = obj
        return ret

    if len(meshes) == 0:
        raise Exception("Please select at least 1 mesh object!")

    bpy.ops.object.mode_set(mode="OBJECT")

    if which_modifier == "Armature":
        for mesh in meshes:
            if mesh.type != "MESH":
                continue
            bpy.context.view_layer.objects.active = mesh
            name = "Armature"
            mod = mesh.modifiers.get(name)
            if mod:
                mesh.modifiers.remove(mod)
            mod = mesh.modifiers.new(name, "ARMATURE")
            move_modifier_to_top(mod)
            mod.object = search_for_avatar_armature(mesh)
            if mod.object == None:
                mod.object = search_for_only_armature()
            mod.show_expanded = mod.object == None
            mod.show_on_cage = True
            mod.show_in_editmode = True
            mod.show_viewport = True
            mod.show_render = True
            mod.use_deform_preserve_volume = True

    elif which_modifier == "DataTransfer":
        for mesh in meshes:
            if mesh.type != "MESH":
                continue
            bpy.context.view_layer.objects.active = mesh
            name = "DataTransfer"
            mod = mesh.modifiers.get(name)
            if mod:
                mesh.modifiers.remove(mod)
            mod = mesh.modifiers.new(name, "DATA_TRANSFER")
            move_modifier_to_top(mod)
            mod.show_expanded = True
            mod.show_on_cage = True
            mod.show_in_editmode = True
            mod.use_vert_data = True
            mod.data_types_verts = {"VGROUP_WEIGHTS"}
            mod.vert_mapping = "POLYINTERP_NEAREST"

    elif which_modifier == "Decimate":
        for mesh in meshes:
            if mesh.type != "MESH":
                continue
            bpy.context.view_layer.objects.active = mesh
            name = "Final - Decimate"
            mod = mesh.modifiers.get(name)
            if mod:
                mesh.modifiers.remove(mod)
            mod = mesh.modifiers.new(name, "DECIMATE")
            mod.show_expanded = False
            mod.show_render = False
            mod.decimate_type = "COLLAPSE"
            mod.ratio = 0.75
            mod.delimit = {"NORMAL", "MATERIAL", "SEAM", "SHARP", "UV"}
            mod.use_dissolve_boundaries = True

            name = "Final - Triangulate"
            mod = mesh.modifiers.get(name)
            if mod:
                mesh.modifiers.remove(mod)
            mod = mesh.modifiers.new(name, "TRIANGULATE")
            mod.show_expanded = False
            mod.show_in_editmode = False
            mod.show_render = False
            mod.min_vertices = 5

    elif which_modifier == "Outline":
        for mesh in meshes:
            if mesh.type != "MESH":
                continue
            bpy.context.view_layer.objects.active = mesh
            name = "-- Outline"
            mod = mesh.modifiers.get(name)
            if mod:
                mesh.modifiers.remove(mod)
            mod = mesh.modifiers.new(name, "SOLIDIFY")
            move_modifier_to_top(mod)
            mod.show_expanded = False
            mod.show_on_cage = False
            mod.show_in_editmode = False
            mod.thickness = -0.001
            mod.use_rim = True
            mod.use_rim_only = False
            mod.use_flip_normals = True
            mod.material_offset = 100
            mod.material_offset_rim = 100
            mod.use_quality_normals = True

            if "-- Outline" in mesh.vertex_groups:
                mod.vertex_group = "-- Outline"

            # If anywhere in the list, remove
            for i in reversed(range(len(mesh.material_slots))):
                if mesh.material_slots[i].name.startswith("-- Outline"):
                    mesh.active_material_index = i
                    bpy.ops.object.material_slot_remove()

            try:
                mat_outline = bpy.data.materials["-- Outline - Black"]
            except:
                # Create it if it doesn't exist

                mat_outline = bpy.data.materials.new(name="-- Outline - Black")
                mesh.active_material_index = len(mesh.material_slots) - 1

            # Reconfigure
            mat_outline.use_backface_culling = True
            mat_outline.blend_method = "HASHED"
            mat_outline.shadow_method = "NONE"
            mat_outline.use_screen_refraction = True

            # Principled BSDF - Transparent Black
            mat_outline.use_nodes = True
            mat_outline.node_tree.nodes.clear()

            # Nodes
            output = mat_outline.node_tree.nodes.new("ShaderNodeOutputMaterial")
            mix = mat_outline.node_tree.nodes.new("ShaderNodeMixShader")
            geometry = mat_outline.node_tree.nodes.new("ShaderNodeNewGeometry")
            transparent = mat_outline.node_tree.nodes.new("ShaderNodeBsdfTransparent")
            principled = mat_outline.node_tree.nodes.new("ShaderNodeBsdfPrincipled")

            # Mix Shader
            mat_outline.node_tree.links.new(mix.outputs[0], output.inputs[0])

            # Geomety "Backface" to "Factor"
            mat_outline.node_tree.links.new(geometry.outputs[6], mix.inputs[0])

            # Principled to Mix Shader 1st
            mat_outline.node_tree.links.new(principled.outputs[0], mix.inputs[1])
            principled.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
            principled.inputs[6].default_value = 0  # Metallic
            principled.inputs[7].default_value = 0  # Specular
            principled.inputs[9].default_value = 1  # Roughness
            principled.inputs[21].default_value = 0.5  # Alpha

            # Transparent to Mix Shader 2nd
            mat_outline.node_tree.links.new(transparent.outputs[0], mix.inputs[2])

            mesh.data.materials.append(mat_outline)

    else:
        raise Exception("Unknown modifier: " + which_modifier)
