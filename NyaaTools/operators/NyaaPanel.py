import bpy
from bpy.props import StringProperty

from ..avatar.get_avatar_layers import get_avatar_layers
from ..common.get_prop import get_prop
from ..consts import PROP_AVATAR_EXPORT_PATH, PROP_AVATAR_LAYERS, PROP_AVATAR_NAME, VERSION


class NyaaPanel(bpy.types.Panel):
    bl_label = "NyaaTools v" + ".".join(str(i) for i in VERSION)
    bl_idname = "OBJECT_PT_NYAAPANEL"
    bl_category = "Tool"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    selectedAvatar: StringProperty(
        name="Selected Avatar",
        default=""
    )

    def draw(self, context):
        layout = self.layout

        obj = bpy.context.active_object
        objs = bpy.context.selected_objects
        has_selection = 0 < len(objs)

        # Deselecting all should count as no selection / no active
        if not has_selection:
            obj = None
            objs = []

        selected_armatures = []
        selected_meshes = []
        for obj in objs:
            if obj.type == "ARMATURE":
                selected_armatures.append(obj)
            elif obj.type == "MESH":
                selected_meshes.append(obj)

        is_armature = len(selected_armatures) == 1
        is_mesh = 0 < len(selected_meshes)

        armature = selected_armatures[0] if is_armature else None

        avatar_name = None
        export_path = None
        avatar_mesh_count = 0
        if is_armature:
            avatar_name = get_prop(armature, PROP_AVATAR_NAME)
            if avatar_name != None and avatar_name.strip() == "":
                avatar_name = None

            export_path = get_prop(armature, PROP_AVATAR_EXPORT_PATH)
            if export_path != None and export_path.strip() == "":
                export_path = None

            if avatar_name != None:
                # Count all meshes that have a get_prop(mesh, PROP_AVATAR_LAYER) == avatar
                for mesh in bpy.data.objects:
                    if mesh.type != "MESH":
                        continue

                    # Get pairs [path_avatar_name, path_layer_name]
                    # If avatar_name == path_avatar_name, merge
                    layers = get_avatar_layers(mesh)
                    for path_avatar_name, path_layer_name in layers:
                        if avatar_name == path_avatar_name:
                            if 0 < len(path_layer_name):
                                avatar_mesh_count += 1

        avatar_layers = None
        avatar_layers_multi_warning = False
        if is_mesh:
            for mesh in selected_meshes:
                if avatar_layers == None:
                    avatar_layers = get_prop(mesh, PROP_AVATAR_LAYERS)
                elif avatar_layers != get_prop(mesh, PROP_AVATAR_LAYERS):
                    avatar_layers_multi_warning = True
                    break

        #############################################
        # Avatar Armature

        if is_armature:
            count = ""
            if avatar_name != None:
                count = " (" + str(avatar_mesh_count) + " meshes)"

            box = layout.box()
            box.label(text="Avatar" + count, icon="OUTLINER_OB_ARMATURE")
            row = box.row(align=True)

            if avatar_name != None:
                op = row.operator(
                    "nyaa.configure_avatar_armature", text="Configure Avatar")
                op.avatar_name = avatar_name
                op.export_path = export_path

                # Right under configure:
                # [Show avatar]
                #   -> *hides non avatar meshes*

                box.label(text="Merge & Export", icon="OUTLINER_OB_ARMATURE")
                row = box.row(align=True)

                row.operator("nyaa.avatar_merge_tool",
                             text="Export: " + avatar_name).avatar_name = avatar_name

            else:
                op = row.operator(
                    "nyaa.configure_avatar_armature", text="Make New Avatar")

        #############################################
        # Avatar Mesh

        if is_mesh:
            box = layout.box()
            box.label(text="Avatar Layer", icon="OUTLINER_OB_ARMATURE")
            row = box.row(align=True)

            # Loop and list all known avatars here:
            # Ex If single object selected:
            # "Avatar Name"
            # [➕ add 1 mesh]  OR  [🗑️ remove 1 mesh]
            #   ->  "Layer Name: ________"    (blanks treated as remove)
            #    A  -> add_avatar_layer(mesh, avatar_name, layer_name)
            #    R  -> remove_avatar_layer(mesh, avatar_name)

        #############################################
        # Mesh

        if is_mesh:
            box = layout.box()
            box.label(text="Mesh Cleanup", icon="OUTLINER_OB_MESH")
            row = box.row(align=True)

            op = row.operator("nyaa.mesh_cleanup", text="All")
            op.vg = True
            op.sk = True
            op.mat = True
            row.operator("nyaa.mesh_cleanup", text="Vertex Groups").vg = True
            row = box.row(align=True)

            row.operator("nyaa.mesh_cleanup", text="Shape Keys").sk = True
            row.operator("nyaa.mesh_cleanup", text="Materials").mat = True

            box.label(text="Add Modifiers", icon="TOOL_SETTINGS")
            row = box.row(align=True)

            row.operator("nyaa.add_modifier",
                         text="Armature").which = "Armature"

            row.operator("nyaa.add_modifier",
                         text="Data Transfer").which = "DataTransfer"

            row = box.row(align=True)

            row = row.split(factor=0.5)
            row.operator("nyaa.add_modifier",
                         text="Decimate").which = "Decimate"

            box.label(text="Modifier with Shape Keys",
                      icon="SHAPEKEY_DATA")
            row = box.row(align=True)

            row.operator("nyaa.apply_top_modifier", text="Apply Top Modifier")

        elif not has_selection:
            box = layout.box()
            box.label(text="Mesh", icon="OUTLINER_OB_MESH")
            box.label(text="Select a mesh to edit.")

        #############################################
        # Armature

        if is_armature:
            box = layout.box()
            box.label(text="Nyaa's Normalization", icon="OUTLINER_OB_ARMATURE")
            row = box.row(align=True)

            row.operator("nyaa.normalize_armature_a_pose",
                         text="A-Pose",
                         icon="ERROR")
            row.operator("nyaa.normalize_armature_t_pose",
                         text="T-Pose",
                         icon="ERROR")

            box.label(text="Quick Pose", icon="OUTLINER_OB_ARMATURE")
            row = box.row(align=True)

            row.operator("nyaa.set_armature_a_pose", text="Set A-Pose")
            row.operator("nyaa.set_armature_t_pose", text="Set T-Pose")

        elif not has_selection:
            box = layout.box()
            box.label(text="Armature",
                      icon="OUTLINER_OB_ARMATURE")
            box.label(text="Select an armature to edit.")

        #############################################

        if not has_selection:
            box = layout.box()
            box.label(text="Atelier Nyaarium", icon="INFO")

            row = box.row(align=True)

            row.operator("ops.open_link", text="Update",
                         icon="WORLD").url = "https://raw.githubusercontent.com/nyaarium/blender-nyaatools/main/nyaatools.py"

            row.operator("ops.open_link", text="GitHub",
                         icon="WORLD").url = "github.com/nyaarium/blender-nyaatools"
