"""
Main panel classes for NyaaTools.
"""

import bpy
from bpy.types import Panel

from ..consts import ISSUES_URL, UPDATE_URL, VERSION
from ..asset.asset_helpers import (
    get_asset_description,
    find_asset_for_mesh,
    get_layer_name_collisions,
)

from .panels_context import get_selection_context


# =============================================================================
# Draw Helpers
# =============================================================================


def draw_asset_meshes_list(layout, asset):
    """Draw the UIList for asset meshes with add/remove/edit buttons."""
    cfg = asset.nyaa_asset

    row = layout.row()
    row.template_list(
        "NYAATOOLS_UL_AssetMeshes",
        "",
        cfg,
        "meshes",
        cfg,
        "active_mesh_index",
        rows=3,
    )

    col = row.column(align=True)
    col.operator("nyaatools.add_selected_meshes", icon="ADD", text="")
    col.operator("nyaatools.remove_mesh", icon="REMOVE", text="")
    col.operator("nyaatools.rename_layer", icon="OUTLINER_OB_FONT", text="")
    col.separator()
    col.operator("nyaatools.edit_mesh_entry", icon="PREFERENCES", text="")
    col.separator()
    col.operator("nyaatools.jump_to_mesh", icon="RESTRICT_SELECT_OFF", text="")


def draw_export_profiles(layout, asset, context):
    """Draw export profiles list with add/edit/remove/run controls."""
    cfg = asset.nyaa_asset
    has_bake_profiles = len(cfg.bake_images) > 0

    if asset.type == "ARMATURE" and len(cfg.meshes) == 0:
        layout.label(text="No meshes assigned", icon="ERROR")
        return

    if len(cfg.export_profiles) == 0:
        box = layout.box()
        box.label(text="No export profiles configured", icon="INFO")
        box.operator(
            "nyaatools.add_export_profile", text="Add Export Profile", icon="ADD"
        )
        return

    if len(cfg.export_profiles) > 0 and 0 <= cfg.active_export_index < len(
        cfg.export_profiles
    ):
        profile = cfg.export_profiles[cfg.active_export_index]

        # Show validation warnings
        if profile.bake_after_export and not has_bake_profiles:
            box = layout.box()
            box.alert = True
            box.label(text='"Bake after export" requires a bake profile', icon="ERROR")

        # Check for layer name collisions (for any export type)
        collisions = get_layer_name_collisions(asset)
        if collisions:
            box = layout.box()
            box.alert = True
            col = box.column(align=True)
            col.label(text="Layer name conflicts with existing objects:", icon="ERROR")
            for layer_name, obj_name in collisions[:3]:  # Show first 3
                col.label(text=f'  "{layer_name}" conflicts with "{obj_name}"')
            if len(collisions) > 3:
                col.label(text=f"  ...and {len(collisions) - 3} more")
            col.label(text="Rename those objects or change layer names.")

        # Export button with appropriate label/icon
        row = layout.row(align=True)
        row.scale_y = 1.2
        if profile.target_type == "collection":
            row.operator(
                "nyaatools.run_export_profile",
                text="Export to Collection",
                icon="ASSET_MANAGER",
            )
        else:
            if profile.bake_after_export:
                row.operator(
                    "nyaatools.run_export_profile",
                    text="Merge, Export, Bake",
                    icon="EXPORT",
                )
            else:
                row.operator(
                    "nyaatools.run_export_profile", text="Merge & Export", icon="EXPORT"
                )

    # Export Profiles (collapsible)
    box = layout.box()
    row = box.row()

    # Icon reflects current export mode
    active_profile = None
    if len(cfg.export_profiles) > 0 and 0 <= cfg.active_export_index < len(
        cfg.export_profiles
    ):
        active_profile = cfg.export_profiles[cfg.active_export_index]
    if active_profile and active_profile.export_static and asset.type == "ARMATURE":
        icon = "OUTLINER_OB_MESH"
    elif asset.type == "ARMATURE":
        icon = "OUTLINER_OB_ARMATURE"
    else:
        icon = "OUTLINER_OB_MESH"

    title = "Export Profile"
    if active_profile:
        desc = get_asset_description(asset, active_profile)
        all_formats = active_profile.bl_rna.properties["format"]
        format_enums = dict(all_formats.enum_items)
        current_format = format_enums.get(active_profile.format, active_profile.format)
        title = "Export Profile: " + current_format.name + " (" + desc + ")"

    row.prop(
        cfg,
        "show_export_profiles",
        icon="TRIA_DOWN" if cfg.show_export_profiles else "TRIA_RIGHT",
        icon_only=True,
        emboss=False,
    )
    row.label(text=title, icon=icon)
    show_export_profiles = cfg.show_export_profiles

    if show_export_profiles:
        row = box.row()
        row.template_list(
            "NYAATOOLS_UL_ExportProfiles",
            "",
            cfg,
            "export_profiles",
            cfg,
            "active_export_index",
            rows=2,
        )

        col = row.column(align=True)
        col.operator("nyaatools.add_export_profile", icon="ADD", text="")
        col.operator("nyaatools.remove_export_profile", icon="REMOVE", text="")
        col.separator()
        col.operator("nyaatools.edit_export_profile", text="", icon="PREFERENCES")


def draw_bake_channels(layout, asset, context):
    """Draw bake channels list with add/edit/remove/run controls."""
    cfg = asset.nyaa_asset
    has_bake_channels = len(cfg.bake_images) > 0
    has_bake_after_export = any(
        profile.bake_after_export for profile in cfg.export_profiles
    )

    box = layout.box()
    row = box.row()

    title = "Bake Channels"
    if has_bake_channels:
        list = []
        for img in cfg.bake_images:
            list.append(img.format)
        title = "Bake Channels: " + ", ".join(list)

    active_profile = None
    if len(cfg.export_profiles) > 0 and 0 <= cfg.active_export_index < len(
        cfg.export_profiles
    ):
        active_profile = cfg.export_profiles[cfg.active_export_index]

    if not active_profile or not active_profile.bake_after_export:
        title += " (Disabled)"

    row.prop(
        cfg,
        "show_bake_channels",
        icon="TRIA_DOWN" if cfg.show_bake_channels else "TRIA_RIGHT",
        icon_only=True,
        emboss=not has_bake_channels and has_bake_after_export,
    )
    row.label(text=title, icon="OUTPUT")

    show_bake_channels = cfg.show_bake_channels
    if show_bake_channels:
        if has_bake_channels:
            row = box.row()
            row.template_list(
                "NYAATOOLS_UL_BakeImages",
                "",
                cfg,
                "bake_images",
                cfg,
                "active_bake_index",
                rows=4,
            )
            col = row.column(align=True)
            col.operator("nyaatools.add_bake_image", icon="ADD", text="")
            col.operator("nyaatools.remove_bake_image", icon="REMOVE", text="")
            col.separator()
            col.operator("nyaatools.edit_bake_image", icon="PREFERENCES", text="")
            col.separator()
            col.operator("nyaatools.load_bake_profile", icon="IMPORT", text="")
        else:
            col = box.column(align=True)
            col.label(text="No bake channels configured", icon="INFO")
            col.operator(
                "nyaatools.load_bake_profile", text="Load Profile", icon="IMPORT"
            )
            col.operator(
                "nyaatools.add_bake_image", text="Add Bake Channel", icon="ADD"
            )


# =============================================================================
# Main Panel
# =============================================================================


class NYAATOOLS_PT_Main(Panel):
    """Main NyaaTools panel."""

    bl_label = "NyaaTools v" + ".".join(str(i) for i in VERSION)
    bl_idname = "NYAATOOLS_PT_Main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "NyaaTools"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        sel = get_selection_context(context)

        if not sel.has_armature and not sel.has_meshes:
            box = layout.box()
            box.label(text="Select objects to see tools", icon="INFO")
            row = box.row(align=True)
            row.operator("ops.open_link", text="Updates", icon="URL").url = UPDATE_URL
            row.operator("ops.open_link", text="Issues?", icon="URL").url = ISSUES_URL


# =============================================================================
# Asset Configuration Subpanel
# =============================================================================


class NYAATOOLS_PT_AssetConfig(Panel):
    """Asset configuration and export."""

    bl_label = "Asset Configuration"
    bl_idname = "NYAATOOLS_PT_AssetConfig"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "NyaaTools"
    bl_parent_id = "NYAATOOLS_PT_Main"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 1

    @classmethod
    def poll(cls, context):
        sel = get_selection_context(context)
        return sel.has_armature or sel.has_meshes

    def draw_header(self, context):
        self.layout.label(text="", icon="OUTLINER_OB_ARMATURE")

    def draw(self, context):
        layout = self.layout
        sel = get_selection_context(context)

        if sel.has_legacy_data:
            box = layout.box()
            box.alert = True
            col = box.column(align=True)
            col.label(text="Legacy data detected!", icon="ERROR")
            col.label(text="Migration required to continue.")
            col.separator()
            col.operator(
                "nyaatools.migrate_legacy_data",
                text="Upgrade Legacy Data",
                icon="FILE_REFRESH",
            )
            return

        # Check if any meshes belong to assets but no assets are selected
        if len(sel.meshes_belonging_to) > 0 and not sel.has_asset:
            # Collect unique assets (same asset might appear multiple times if multiple meshes belong to it)
            unique_assets = {}
            for asset_obj, layer_name in sel.meshes_belonging_to:
                if asset_obj not in unique_assets:
                    unique_assets[asset_obj] = []
                unique_assets[asset_obj].append(layer_name)

            box = layout.box()
            box.label(text="Selected meshes belong to:", icon="INFO")
            for asset_obj in unique_assets.keys():
                row = box.row(align=True)
                op = row.operator(
                    "nyaatools.jump_to_asset",
                    text=asset_obj.nyaa_asset.asset_name,
                    icon="FORWARD",
                )
                op.asset_name = asset_obj.name
            return

        if len(sel.meshes) == 1 and len(sel.armatures) == 0:
            mesh = sel.meshes[0]

            if hasattr(mesh, "nyaa_asset") and mesh.nyaa_asset.is_asset:
                self._draw_asset_config(layout, mesh, sel)
                return

            layout.label(text="This mesh is not part of any asset.")
            layout.operator(
                "nyaatools.create_asset_from_mesh", text="Create Asset", icon="ADD"
            )
            return

        if sel.exactly_one_armature:
            arm = sel.armature

            if hasattr(arm, "nyaa_asset") and arm.nyaa_asset.is_asset:
                self._draw_asset_config(layout, arm, sel)
            else:
                layout.label(text="This armature is not configured.")
                layout.operator(
                    "nyaatools.mark_as_asset", text="Mark as Asset", icon="ADD"
                )
            return

        # Check if we have exactly one asset in selection (mesh asset + other meshes)
        if sel.has_asset:
            self._draw_asset_config(layout, sel.asset, sel)
            return

        layout.label(text="Select a single armature or mesh")

    def _draw_asset_config(self, layout, asset, sel):
        """Draw the full asset configuration UI."""
        cfg = asset.nyaa_asset

        box = layout.box()
        row = box.row(align=True)

        row.label(text="", icon="PACKAGE")
        row.prop(cfg, "asset_name", text="")

        # Show "Destroy Asset" button
        row = box.row()
        row.label(text="")
        row.operator("nyaatools.unmark_asset", text="Destroy Asset", icon="X")

        layout.separator()

        draw_export_profiles(layout, asset, bpy.context)

        draw_bake_channels(layout, asset, bpy.context)


# =============================================================================
# Asset Parts Subpanel
# =============================================================================


class NYAATOOLS_PT_AssetParts(Panel):
    """Meshes assigned to the asset."""

    bl_label = "Asset Parts"
    bl_idname = "NYAATOOLS_PT_AssetParts"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "NyaaTools"
    bl_parent_id = "NYAATOOLS_PT_Main"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 2

    @classmethod
    def poll(cls, context):
        sel = get_selection_context(context)
        return sel.has_asset

    def draw_header(self, context):
        sel = get_selection_context(context)
        icon = "ARMATURE_DATA" if sel.asset.type == "ARMATURE" else "MESH_DATA"
        self.layout.label(text="", icon=icon)

    def draw(self, context):
        layout = self.layout
        sel = get_selection_context(context)

        if sel.has_legacy_data:
            layout.label(text="Migration required first", icon="ERROR")
            return

        layout.label(text="Assigned Meshes:")
        draw_asset_meshes_list(layout, sel.asset)
