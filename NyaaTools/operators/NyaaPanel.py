import bpy
from bpy.props import StringProperty

from ..avatar.get_avatar_layers import get_avatar_layers
from ..common.get_prop import get_prop
from ..common.has_value import has_value
from ..consts import PROP_AVATAR_EXPORT_PATH, PROP_AVATAR_LAYERS, PROP_AVATAR_NAME, ISSUES_URL, UPDATE_URL, VERSION


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
        error = None

        # Don't consider it a selection if active object with no selection
        has_selection = False

        is_armature = False
        is_avatar = False
        is_mesh = False
        armature = None
        avatar_name = None
        export_path = None

        selected_armatures = []
        selected_meshes = []

        mesh_layers = []

        try:
            # Determine mesh & armature selection
            for obj in bpy.context.selected_objects:
                if obj.type == "ARMATURE":
                    selected_armatures.append(obj)

                    if len(selected_armatures) == 1:
                        # Select this armature
                        armature = obj
                        is_armature = True
                        avatar_name = get_prop(armature, PROP_AVATAR_NAME)
                        export_path = get_prop(
                            armature, PROP_AVATAR_EXPORT_PATH)
                        is_avatar = has_value(avatar_name)
                    if 1 < len(selected_armatures):
                        # Deselect armature
                        armature = None
                        is_armature = False
                        avatar_name = None
                        export_path = None
                        is_avatar = False

                elif obj.type == "MESH":
                    selected_meshes.append(obj)

                    is_mesh = True

            # If avatar selection, check avatar layers (meshes using this)
            if is_avatar:
                for mesh in bpy.data.objects:
                    # Pairs of [path_avatar_name, path_layer_name]
                    layers = get_avatar_layers(mesh)

                    # Filter layers to only those using this avatar
                    for layer in layers:
                        if layer[0] == avatar_name:
                            mesh_layers.append([mesh, layer[1]])
                    print(mesh_layers)

            # If mesh selection, check mesh avatars
            # if is_mesh:
            #     for mesh in selected_meshes:
            #         avatar_layers = get_avatar_layers(mesh)
            #         print(avatar_layers)

            has_selection = is_armature or is_mesh

        except Exception as e:
            error = e
            print("Error in NyaaPanel:")
            print(e)

        #############################################
        #############################################
        # Begin layout

        layout = self.layout

        if error != None:
            box = layout.box()
            box.label(text="An error occurred.")
            box.label(text="Please report the issue.")
            box.label(text="")
            box.label(text=str(error))

        #############################################
        # Avatar Armature

        if is_armature:
            mesh_count = ""
            if is_avatar:
                mesh_count = " (" + str(len(mesh_layers)) + " meshes)"

            box = layout.box()
            box.label(text="Avatar" + mesh_count, icon="OUTLINER_OB_ARMATURE")
            row = box.row(align=True)

            if is_avatar:
                op = row.operator(
                    "nyaa.configure_avatar_armature", text="Configure Avatar")
                op.avatar_name = avatar_name
                op.export_path = export_path

                if 0 < len(mesh_layers):
                    box.label(text="Merge & Export", icon="OUTLINER_OB_ARMATURE")
                    row = box.row(align=True)

                    row.operator("nyaa.avatar_merge_tool",
                                text="Export: " + avatar_name).avatar_name = avatar_name
                else:
                    box.label(text="No meshes assigned", icon="OUTLINER_OB_ARMATURE")

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

            row.operator("ops.open_link", text="Updates",
                         icon="WORLD").url = UPDATE_URL

            row.operator("ops.open_link", text="Issues?",
                         icon="WORLD").url = ISSUES_URL
