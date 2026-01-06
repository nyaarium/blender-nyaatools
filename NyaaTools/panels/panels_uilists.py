"""
UIList classes for NyaaTools panel.
"""

import bpy

from bpy.types import UIList


def _get_active_export_profile_includes_colliders(data):
    """Check if the active export profile includes UE colliders."""
    if not hasattr(data, "export_profiles"):
        return True
    if len(data.export_profiles) == 0:
        return True
    if data.active_export_index < 0 or data.active_export_index >= len(
        data.export_profiles
    ):
        return True
    profile = data.export_profiles[data.active_export_index]
    # VotV always includes colliders
    if profile.format == "votv":
        return True
    return profile.include_ue_colliders


class NYAATOOLS_UL_AssetMeshes(UIList):
    """UIList for displaying meshes assigned to an asset."""

    bl_idname = "NYAATOOLS_UL_AssetMeshes"

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)

            # Check if colliders are included in active export profile
            include_colliders = _get_active_export_profile_includes_colliders(data)

            # Dim collider rows if not included in export
            if item.is_ue_collider and not include_colliders:
                row.active = False

            # Layer name
            row.label(text=item.layer_name)

            # Mesh name with appropriate icon
            if item.mesh_object:
                mesh_icon = "PHYSICS" if item.is_ue_collider else "OUTLINER_OB_MESH"
                row.label(text=item.mesh_object.name, icon=mesh_icon)
            else:
                row.label(text="(deleted)", icon="ERROR")
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            mesh_icon = "PHYSICS" if item.is_ue_collider else "OUTLINER_OB_MESH"
            layout.label(text="", icon=mesh_icon)

    def filter_items(self, context, data, propname):
        """Sort items: Layer alphabetically -> Mesh name alphabetically -> Colliders last."""
        items = getattr(data, propname)
        helper_funcs = bpy.types.UI_UL_list

        # Default: show all items
        flt_flags = [self.bitflag_filter_item] * len(items)

        # Build sort keys: (is_collider, layer_name, mesh_name)
        # Colliders sort last (True > False), then layer alpha, then mesh alpha
        def sort_key(item):
            mesh_name = item.mesh_object.name if item.mesh_object else ""
            return (item.is_ue_collider, item.layer_name.lower(), mesh_name.lower())

        # Create sorted order indices
        sorted_items = sorted(enumerate(items), key=lambda x: sort_key(x[1]))
        flt_neworder = [i for i, _ in sorted_items]

        return flt_flags, flt_neworder


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


UILIST_CLASSES = [
    NYAATOOLS_UL_AssetMeshes,
    NYAATOOLS_UL_ExportProfiles,
    NYAATOOLS_UL_BakeImages,
]
