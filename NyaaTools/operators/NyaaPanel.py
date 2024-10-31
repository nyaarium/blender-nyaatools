import bpy
from bpy.props import StringProperty

from ..avatar.get_avatar_layers import get_avatar_layers
from ..common.get_prop import get_prop
from ..common.has_value import has_value
from ..consts import (
    PROP_AVATAR_EXPORT_PATH,
    PROP_AVATAR_NAME,
    ISSUES_URL,
    UPDATE_URL,
    VERSION,
)


class NyaaPanel(bpy.types.Panel):
    bl_label = "NyaaTools v" + ".".join(str(i) for i in VERSION)
    bl_idname = "OBJECT_PT_NYAAPANEL"
    bl_category = "NyaaTools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    # TODO: Reimplement to not operate in draw context
    # Modal? Something else?
    def draw(self, context):
        error = None

        # Don't consider it a selection if active object with no selection
        has_selection = False

        is_armature = False
        is_avatar = False
        is_exactly_2_armatures = False
        is_mesh = False
        armature = None
        avatar_name = None
        export_path = None

        selected_armatures = []
        selected_meshes = []

        all_selected_meshes_using_this_avatar = True
        no_selected_meshes_using_this_avatar = True

        # Dict of [path_layer_name] = [meshes]
        selected_avatar_layers = {}
        unassigned_meshes = []

        avatar_layers = {}
        mesh_layers_count = 0

        #############################################

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
                        export_path = get_prop(armature, PROP_AVATAR_EXPORT_PATH)
                        is_avatar = has_value(avatar_name)
                    elif 1 < len(selected_armatures):
                        # Deselect armature
                        armature = None
                        is_armature = False
                        avatar_name = None
                        export_path = None
                        is_avatar = False

                elif obj.type == "MESH":
                    selected_meshes.append(obj)

                    is_mesh = True

            if len(selected_armatures) == 2 and len(selected_meshes) == 0:
                is_exactly_2_armatures = True

            if is_avatar:
                for mesh in selected_meshes:
                    # Pairs of [path_avatar_name, path_layer_name]
                    layers = get_avatar_layers(mesh)

                    is_using_this_avatar = False
                    for layer in layers:
                        path_avatar_name = layer[0]
                        path_layer_name = layer[1]
                        if path_avatar_name == avatar_name:
                            is_using_this_avatar = True

                            # Add to selected_avatar_layers
                            if not path_layer_name in selected_avatar_layers:
                                selected_avatar_layers[path_layer_name] = []
                            selected_avatar_layers[path_layer_name].append(mesh)

                            break
                    if is_using_this_avatar:
                        no_selected_meshes_using_this_avatar = False
                    else:
                        all_selected_meshes_using_this_avatar = False
                        unassigned_meshes.append(mesh)

                # ISSUE: This is expensive in larger scenes. Maybe remove this section
                # If avatar selection, check avatar layers (meshes using this)
                for mesh in bpy.data.objects:
                    # Pairs of [path_avatar_name, path_layer_name]
                    layers = get_avatar_layers(mesh)

                    # Filter layers to only those using this avatar
                    for layer in layers:
                        path_avatar_name = layer[0]
                        path_layer_name = layer[1]
                        if path_avatar_name == avatar_name:
                            # If not defined, init array
                            if not path_layer_name in avatar_layers:
                                avatar_layers[path_layer_name] = []

                            avatar_layers[path_layer_name].append(mesh)

                            mesh_layers_count += 1

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
            title_text = "Avatar (not configured)"
            if is_avatar:
                title_text = "Avatar: " + avatar_name

            box = layout.box()
            box.label(text=title_text, icon="OUTLINER_OB_ARMATURE")
            row = box.row(align=True)

            if is_avatar:
                op = row.operator(
                    "nyaa.configure_avatar_armature", text="🔧 Reconfigure"
                )
                op.avatar_name = avatar_name
                op.export_path = export_path

                row = box.row(align=True)

                if 0 < mesh_layers_count:
                    op = row.operator(
                        "nyaa.avatar_merge_export", text="📦 Merge & Export"
                    )
                    op.avatar_name = avatar_name
                else:
                    box.label(text="No meshes assigned", icon="ERROR")
                    box.label(text="Select this armature and some meshes")

            else:
                op = row.operator(
                    "nyaa.configure_avatar_armature", text="Make New Avatar"
                )
                op.avatar_name = ""
                op.export_path = "./Export.fbx"

        elif 1 < len(selected_armatures):
            # To configure Avatar, select 1 armature
            pass

        else:
            box = layout.box()
            box.label(text="Avatar Armature", icon="OUTLINER_OB_ARMATURE")
            box.label(text="Select an armature")

        #############################################
        # Selected Avatar Meshes

        if is_mesh:
            box = layout.box()
            box.label(text="Selected Avatar Meshes", icon="OUTLINER_OB_MESH")
            row = box.row(align=True)

            if is_avatar:
                if 0 < len(selected_avatar_layers):
                    # List meshes in selected_avatar_layers
                    for path_layer_name in selected_avatar_layers:
                        # Display layer name
                        row.label(text=path_layer_name)

                        meshes = selected_avatar_layers[path_layer_name]
                        for mesh in meshes:
                            row = box.row(align=True)
                            split = row.split(factor=0.1)
                            split.label(text="")
                            split.label(text=mesh.name)

                        row = box.row(align=True)

                    if 0 < len(unassigned_meshes):
                        # Display unassigned meshes
                        row.label(text="(Unassigned)")
                        for mesh in unassigned_meshes:
                            row = box.row(align=True)
                            split = row.split(factor=0.1)
                            split.label(text="")
                            split.label(text=mesh.name)
                else:
                    box.label(text="(no meshes assigned)")

                row = box.row(align=True)

                c = str(len(selected_meshes))
                if all_selected_meshes_using_this_avatar:
                    # Remove selection action
                    op = row.operator(
                        "nyaa.remove_meshes_from_avatar",
                        text="➖ Remove " + c + " from avatar",
                    )
                elif no_selected_meshes_using_this_avatar:
                    # Add selection action
                    text = ""
                    if len(selected_meshes) == 1:
                        text = "➕ Add " + c + " to avatar"
                    else:
                        text = "🔗 Combine " + c + " to single layer"
                    op = row.operator("nyaa.configure_meshes_on_avatar", text=text)
                    if len(selected_meshes) == 1:
                        op.layer_name = selected_meshes[0].name
                    else:
                        op.layer_name = ""
                else:
                    # Recombine selection action
                    op = row.operator(
                        "nyaa.configure_meshes_on_avatar",
                        text="🔗 Recombine " + c + " to single layer",
                    )
                    op.layer_name = ""

            else:
                row.label(text="(no armature selected)")

        elif len(selected_meshes) == 0:
            box = layout.box()
            box.label(text="Selected Avatar Meshes", icon="OUTLINER_OB_MESH")
            box.label(text="Select some meshes")

        #############################################
        # Mesh Tools

        if is_mesh:
            box = layout.box()
            box.label(text="Mesh Cleanup", icon="OUTLINER_OB_MESH")
            row = box.row(align=True)

            op = row.operator("nyaa.mesh_cleanup", text="All")
            op.vg = True
            op.sk = True
            op.mat = True

            op = row.operator("nyaa.mesh_cleanup", text="Vertex Groups")
            op.vg = True
            op.sk = False
            op.mat = False
            row = box.row(align=True)

            op = row.operator("nyaa.mesh_cleanup", text="Shape Keys")
            op.vg = False
            op.sk = True
            op.mat = False

            op = row.operator("nyaa.mesh_cleanup", text="Materials")
            op.vg = False
            op.sk = False
            op.mat = True

            box.label(text="Add Modifiers", icon="TOOL_SETTINGS")
            row = box.row(align=True)

            op = row.operator("nyaa.add_modifier", text="Armature")
            op.which_modifier = "Armature"

            op = row.operator("nyaa.add_modifier", text="Data Transfer")
            op.which_modifier = "DataTransfer"

            # row = box.row(align=True)

            # op = row.operator("nyaa.add_modifier", text="Decimate")
            # op.which_modifier = "Decimate (disabled until fixed)"

            # op = row.operator("nyaa.add_modifier", text="Outline")
            # op.which_modifier = "Outline (disabled until fixed)"

            # To fill in an empty cell
            # row = row.split(factor=0.5)

            box.label(text="Modifier with Shape Keys", icon="SHAPEKEY_DATA")
            row = box.row(align=True)

            row.operator("przemir.apply_top_modifier", text="Apply Top Modifier")

        elif not has_selection:
            box = layout.box()
            box.label(text="Mesh", icon="OUTLINER_OB_MESH")
            box.label(text="Select a mesh to edit.")

        #############################################
        # Armature Tools

        if is_armature or is_exactly_2_armatures:
            box = layout.box()
            box.label(text="Armature", icon="OUTLINER_OB_ARMATURE")
            row = box.row(align=True)

            if is_armature:
                op = row.operator(
                    "nyaa.select_standard_bones", text="Select Standard Bones"
                )

                row = box.row(align=True)

                op = row.operator("nyaa.dissolve_bones", text="Dissolve Bones")

                box = layout.box()
                box.label(text="Nyaa's Normalization", icon="OUTLINER_OB_ARMATURE")

                row = box.row(align=True)
                row.label(text="Don't touch unless you're")
                row = box.row(align=True)
                row.label(text="mocap/animating in Blender")
                
                row = box.row(align=True)

                op = row.operator("nyaa.normalize_armature_rename", text="Rename Bones")

                row = box.row(align=True)

                op = row.operator(
                    "nyaa.normalize_armature_at_pose", text="A-Pose", icon="ERROR"
                )
                op.which_pose = "a-pose"
                op.apply_pose = True

                op = row.operator(
                    "nyaa.normalize_armature_at_pose", text="T-Pose", icon="ERROR"
                )
                op.which_pose = "t-pose"
                op.apply_pose = True

            if is_exactly_2_armatures:
                op = row.operator("nyaa.merge_armatures", text="Merge 2 Armatures")

        if is_exactly_2_armatures:
            box = layout.box()
            box.label(text="Nyaa's Normalization", icon="OUTLINER_OB_ARMATURE")

            row = box.row(align=True)
            op = row.operator("nyaa.normalize_armature_retarget", text="Retarget Armature")

        elif not has_selection:
            box = layout.box()
            box.label(text="Armature", icon="OUTLINER_OB_ARMATURE")
            box.label(text="Select an armature to edit")

        #############################################

        if not has_selection:
            box = layout.box()
            box.label(text="Atelier Nyaarium", icon="INFO")

            row = box.row(align=True)

            row.operator("ops.open_link", text="Updates", icon="WORLD").url = UPDATE_URL

            row.operator("ops.open_link", text="Issues?", icon="WORLD").url = ISSUES_URL
