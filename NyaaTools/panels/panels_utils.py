"""
Utility panel classes for NyaaTools (Mesh Tools, Armature Tools, Normalization).
"""

from bpy.types import Panel

from ..consts import VERSION
from .panels_context import get_selection_context


# =============================================================================
# Mesh Tools Subpanel
# =============================================================================


class NYAATOOLS_PT_MeshTools(Panel):
    """Mesh cleanup and utilities."""

    bl_label = "Mesh Tools"
    bl_idname = "NYAATOOLS_PT_MeshTools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "NyaaTools"
    bl_parent_id = "NYAATOOLS_PT_Main"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 3

    @classmethod
    def poll(cls, context):
        sel = get_selection_context(context)
        return sel.has_armature or sel.has_meshes

    def draw_header(self, context):
        self.layout.label(text="", icon="MESH_DATA")

    def draw(self, context):
        layout = self.layout
        sel = get_selection_context(context)

        if not sel.has_meshes:
            layout.label(text="Select meshes to see tools")
            return

        box = layout.box()
        box.label(text="Cleanup", icon="BRUSH_DATA")
        row = box.row(align=True)

        op = row.operator("nyaa.mesh_cleanup", text="All")
        op.vg = True
        op.sk = True
        op.mat = True

        row = box.row(align=True)
        op = row.operator("nyaa.mesh_cleanup", text="Vertex Groups")
        op.vg = True
        op.sk = False
        op.mat = False

        op = row.operator("nyaa.mesh_cleanup", text="Shape Keys")
        op.vg = False
        op.sk = True
        op.mat = False

        row = box.row(align=True)
        op = row.operator("nyaa.mesh_cleanup", text="Materials")
        op.vg = False
        op.sk = False
        op.mat = True

        box = layout.box()
        box.label(text="Add Modifiers", icon="MODIFIER")
        row = box.row(align=True)
        op = row.operator("nyaa.add_modifier", text="Armature")
        op.which_modifier = "Armature"
        op = row.operator("nyaa.add_modifier", text="Data Transfer")
        op.which_modifier = "DataTransfer"

        box = layout.box()
        box.label(text="Image Utilities", icon="IMAGE_DATA")

        row = box.row(align=True)
        op = row.operator("nyaa.image_packer", text="Pack All", icon="PACKAGE")
        op.pack = True
        op.unpack = False
        op = row.operator("nyaa.image_packer", text="Unpack All", icon="UGLYPACKAGE")
        op.pack = False
        op.unpack = True

        row = box.row(align=True)
        row.operator("nyaa.check_image_formats", text="Check")
        row.operator("nyaa.rename_packed_images", text="Fix Names")

        row = box.row(align=True)
        row.operator("nyaa.help_image_formats", text="???", icon="QUESTION")

        box = layout.box()
        box.label(text="Modifier with Shape Keys", icon="SHAPEKEY_DATA")
        box.operator("nyaa.apply_modifier_shape_keys_uv", text="Apply Top Modifier")


# =============================================================================
# Armature Tools Subpanel
# =============================================================================


class NYAATOOLS_PT_ArmatureTools(Panel):
    """Armature utilities."""

    bl_label = "Armature Tools"
    bl_idname = "NYAATOOLS_PT_ArmatureTools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "NyaaTools"
    bl_parent_id = "NYAATOOLS_PT_Main"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 4

    @classmethod
    def poll(cls, context):
        sel = get_selection_context(context)
        return sel.has_armature or sel.has_meshes

    def draw_header(self, context):
        self.layout.label(text="", icon="BONE_DATA")

    def draw(self, context):
        layout = self.layout
        sel = get_selection_context(context)

        if not sel.has_armature:
            layout.label(text="Select armature(s) to see tools")
            return

        if sel.exactly_one_armature:
            box = layout.box()
            box.label(text="Bone Utilities", icon="BONE_DATA")
            box.operator("nyaa.select_standard_bones", text="Select Standard Bones")
            box.operator("nyaa.dissolve_bones", text="Dissolve Bones")

        if sel.exactly_two_armatures:
            box = layout.box()
            box.label(text="Merge Armatures", icon="CON_ARMATURE")
            box.operator("nyaa.merge_armatures", text="Merge 2 Armatures")


# =============================================================================
# Normalization Subpanel (for humanoid assets)
# =============================================================================


class NYAATOOLS_PT_Normalization(Panel):
    """Nyaa's Normalization tools (experimental)."""

    bl_label = "Nyaa's Normalization"
    bl_idname = "NYAATOOLS_PT_Normalization"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "NyaaTools"
    bl_parent_id = "NYAATOOLS_PT_Main"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 6

    @classmethod
    def poll(cls, context):
        if VERSION != (0, 0, 0):
            # Only show in development
            return False

        sel = get_selection_context(context)
        if sel.has_asset and sel.is_humanoid:
            return True
        return sel.has_armature

    def draw_header(self, context):
        self.layout.label(text="", icon="EXPERIMENTAL")

    def draw(self, context):
        layout = self.layout
        sel = get_selection_context(context)

        if not sel.has_armature:
            layout.label(text="Select armature(s) to see tools")
            return

        layout.label(text="Don't touch unless you're", icon="ERROR")
        layout.label(text="mocap/animating in Blender")

        if sel.exactly_one_armature:
            row = layout.row(align=True)
            row.operator("nyaa.normalize_armature_rename", text="Rename Bones")
            row.operator("nyaa.armature_clear_custom_objects", text="Clear Custom")

            row = layout.row(align=True)
            op = row.operator("nyaa.normalize_armature_at_pose", text="A-Pose")
            op.which_pose = "a-pose"
            op.apply_pose = True

            op = row.operator("nyaa.normalize_armature_at_pose", text="T-Pose")
            op.which_pose = "t-pose"
            op.apply_pose = True

        if sel.exactly_two_armatures:
            layout.operator(
                "nyaa.normalize_armature_retarget", text="Retarget Armature"
            )
