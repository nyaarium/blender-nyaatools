"""
UIList classes for NyaaTools panel.
"""

from bpy.types import UIList


class NYAATOOLS_UL_AssetMeshes(UIList):
    """UIList for displaying meshes assigned to an asset."""

    bl_idname = "NYAATOOLS_UL_AssetMeshes"

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            row.label(text=item.layer_name)
            if item.mesh_object:
                row.label(text=item.mesh_object.name, icon="OUTLINER_OB_MESH")
            else:
                row.label(text="(deleted)", icon="ERROR")
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text="", icon="OUTLINER_OB_MESH")


class NYAATOOLS_UL_ExportProfiles(UIList):
    """UIList for displaying export profiles."""

    bl_idname = "NYAATOOLS_UL_ExportProfiles"

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)

            # Target type icon
            if item.target_type == "collection":
                row.label(text="", icon="ASSET_MANAGER")
            else:
                format_icons = {
                    "fbx": "FILE_3D",
                    "obj": "FILE_3D",
                    "votv": "GHOST_ENABLED",
                }
                format_labels = {"fbx": "FBX", "obj": "OBJ", "votv": "VotV"}
                row.label(
                    text=format_labels.get(item.format, "?"),
                    icon=format_icons.get(item.format, "FILE"),
                )

            # Path or collection name
            if item.target_type == "collection":
                row.label(text="__Export__")
            else:
                path_display = (
                    item.path if len(item.path) < 30 else "..." + item.path[-27:]
                )
                row.label(text=path_display)

            # Option indicators
            indicators = []
            if item.export_static:
                indicators.append("Static")
            if item.bake_after_export:
                indicators.append("Bake")
            if indicators:
                row.label(text=f"[{', '.join(indicators)}]")
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            target_icon = (
                "ASSET_MANAGER" if item.target_type == "collection" else "EXPORT"
            )
            layout.label(text="", icon=target_icon)


class NYAATOOLS_UL_BakeImages(UIList):
    """UIList for displaying bake image configurations."""

    bl_idname = "NYAATOOLS_UL_BakeImages"

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            row.label(text=item.format, icon="IMAGE_DATA")
            # Show resolution with optimize indicator
            res_text = f"{item.width}x{item.height}"
            if item.optimize_resolution:
                res_text = f"<={res_text}"
            row.label(text=res_text)
            row.label(text=item.image_type.upper())
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text="", icon="IMAGE_DATA")


class NYAATOOLS_UL_AvatarMeshes(UIList):
    """UIList for displaying meshes assigned to an avatar (legacy compatibility)."""

    bl_idname = "NYAATOOLS_UL_AvatarMeshes"

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            row.label(text=item.layer_name)
            if item.mesh_object:
                row.label(text=item.mesh_object.name, icon="OUTLINER_OB_MESH")
            else:
                row.label(text="(deleted)", icon="ERROR")
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text="", icon="OUTLINER_OB_MESH")


UILIST_CLASSES = [
    NYAATOOLS_UL_AssetMeshes,
    NYAATOOLS_UL_ExportProfiles,
    NYAATOOLS_UL_BakeImages,
    NYAATOOLS_UL_AvatarMeshes,
]
