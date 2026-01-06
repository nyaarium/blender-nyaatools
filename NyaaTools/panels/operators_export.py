"""
Export profile operators for NyaaTools panel.
"""

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, StringProperty

from .panels_context import SelectionContext, tag_view3d_redraw
from ..asset.asset_helpers import get_layer_name_collisions


def validate_export_profile(
    target_type: str,
    path: str,
    format: str,
    bake_after_export: bool,
    has_bake_profiles: bool,
) -> tuple[bool, str]:
    """
    Validate export profile configuration.
    Returns (is_valid, error_message).
    """
    if target_type == "collection":
        if bake_after_export and not has_bake_profiles:
            return False, '"Bake after export" requires bake profiles to be configured'
        return True, ""

    # File export validation (collection exports don't need path validation)
    if not path:
        return False, "Path is required"

    path_lower = path.lower().rstrip("/\\")

    is_directory = path.endswith("/") or path.endswith("\\")
    if not is_directory:
        if "." in path.split("/")[-1].split("\\")[-1]:
            if path_lower.endswith(".fbx"):
                if format != "fbx":
                    return False, "FBX file requires FBX format"
            elif path_lower.endswith(".obj"):
                if format not in ("obj", "votv"):
                    return False, "OBJ file requires OBJ or VotV format"
            else:
                return False, "Unsupported file extension"
        else:
            is_directory = True

    if bake_after_export and not has_bake_profiles:
        return False, '"Bake after export" requires bake profiles to be configured'

    return True, ""


class NYAATOOLS_OT_AddExportProfile(Operator):
    """Add a new export profile"""

    bl_idname = "nyaatools.add_export_profile"
    bl_label = "Add Export Profile"
    bl_options = {"REGISTER", "UNDO"}

    target_type: EnumProperty(
        name="Target",
        items=[
            ("file", "File", "Export to filesystem"),
            (
                "collection",
                "Collection",
                "Export to __Export__ collection as Blender asset",
            ),
        ],
        default="file",
    )
    path: StringProperty(name="Path", default="", subtype="FILE_PATH")
    format: EnumProperty(
        name="Format",
        items=[
            ("fbx", "FBX", "Export as FBX (Unity/Unreal)"),
            ("obj", "OBJ", "Export as OBJ (static mesh)"),
            ("votv", "VotV", "Export for Voices of the Void"),
        ],
        default="fbx",
    )
    export_static: BoolProperty(
        name="Export as Static",
        default=False,
        description="Apply pose and modifiers, remove armature (exports as static mesh)",
    )
    bake_after_export: BoolProperty(
        name="Bake Textures After Export",
        default=False,
        description="Auto-bake textures after export using configured bake profiles",
    )
    include_ue_colliders: BoolProperty(
        name="Include UE Colliders",
        default=False,
        description="Include Unreal Engine convex-collision meshes (UCX_) in export",
    )

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        return sel.has_asset

    def invoke(self, context, event):
        if not self.path:
            self.path = "./"
        self.include_ue_colliders = False
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        has_bake_profiles = len(cfg.bake_images) > 0

        layout.label(text="Export Profile", icon="EXPORT")

        # Target type selector
        layout.prop(self, "target_type", expand=True)

        # File-specific options
        if self.target_type == "file":
            layout.separator()
            layout.prop(self, "path")

            row = layout.row()
            row.label(text="Format:")
            row.prop(self, "format", text="")

        # Armature-specific option
        if sel.asset.type == "ARMATURE":
            layout.separator()
            layout.prop(self, "export_static")

        # Bake option
        layout.prop(self, "bake_after_export")

        # Meta Objects section
        layout.separator()
        box = layout.box()
        box.label(text="Meta Objects", icon="PHYSICS")
        row = box.row()
        row.prop(self, "include_ue_colliders")

        # VotV forces colliders on
        if self.format == "votv":
            row.enabled = False
            box.label(text="VotV requires UCX_ colliders", icon="INFO")

        # Validation
        is_valid, error = validate_export_profile(
            self.target_type,
            self.path,
            self.format,
            self.bake_after_export,
            has_bake_profiles,
        )
        if not is_valid:
            box = layout.box()
            box.alert = True
            box.row().label(text=error, icon="ERROR")

        # Help text
        layout.separator()
        col = layout.column(align=True)
        col.scale_y = 0.8
        if self.target_type == "collection":
            col.label(text="• __Export__ collection will be purged", icon="INFO")
        else:
            col.label(text="• Folder path (ends with /): uses asset name", icon="INFO")
            col.label(text="• File path (.fbx): direct export, FBX only", icon="INFO")
            col.label(
                text="• File path (.obj): direct export, OBJ or VotV", icon="INFO"
            )

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        has_bake_profiles = len(cfg.bake_images) > 0

        is_valid, error = validate_export_profile(
            self.target_type,
            self.path,
            self.format,
            self.bake_after_export,
            has_bake_profiles,
        )
        if not is_valid:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        # VotV forces colliders on
        include_colliders = self.include_ue_colliders or self.format == "votv"

        profile = cfg.export_profiles.add()
        profile.target_type = self.target_type
        profile.path = self.path
        profile.format = self.format
        profile.export_static = self.export_static
        profile.bake_after_export = self.bake_after_export
        profile.include_ue_colliders = include_colliders
        cfg.active_export_index = len(cfg.export_profiles) - 1

        tag_view3d_redraw(context)

        if self.target_type == "collection":
            self.report({"INFO"}, "Added collection export profile")
        else:
            self.report(
                {"INFO"},
                f"Added file export profile: {self.format.upper()} → {self.path}",
            )
        return {"FINISHED"}


class NYAATOOLS_OT_EditExportProfile(Operator):
    """Edit the selected export profile"""

    bl_idname = "nyaatools.edit_export_profile"
    bl_label = "Edit Export Profile"
    bl_options = {"REGISTER", "UNDO"}

    target_type: EnumProperty(
        name="Target",
        items=[
            ("file", "File", "Export to filesystem"),
            (
                "collection",
                "Collection",
                "Export to __Export__ collection as Blender asset",
            ),
        ],
        default="file",
    )
    path: StringProperty(name="Path", default="", subtype="FILE_PATH")
    format: EnumProperty(
        name="Format",
        items=[
            ("fbx", "FBX", "Export as FBX (Unity/Unreal)"),
            ("obj", "OBJ", "Export as OBJ (static mesh)"),
            ("votv", "VotV", "Export for Voices of the Void"),
        ],
        default="fbx",
    )
    export_static: BoolProperty(
        name="Export as Static",
        default=False,
        description="Apply pose and modifiers, remove armature (exports as static mesh)",
    )
    bake_after_export: BoolProperty(
        name="Bake Textures After Export",
        default=False,
        description="Auto-bake textures after export using configured bake profiles",
    )
    include_ue_colliders: BoolProperty(
        name="Include UE Colliders",
        default=False,
        description="Include Unreal Engine convex-collision meshes (UCX_) in export",
    )

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        if not sel.has_asset:
            return False
        return len(sel.asset.nyaa_asset.export_profiles) > 0

    def invoke(self, context, event):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        profile = cfg.export_profiles[cfg.active_export_index]
        self.target_type = profile.target_type
        self.path = profile.path
        self.format = profile.format
        self.export_static = profile.export_static
        self.bake_after_export = profile.bake_after_export
        self.include_ue_colliders = profile.include_ue_colliders
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        has_bake_profiles = len(cfg.bake_images) > 0

        layout.label(text="Edit Export Profile", icon="EXPORT")

        # Target type selector
        layout.prop(self, "target_type", expand=True)

        # File-specific options
        if self.target_type == "file":
            layout.separator()
            layout.prop(self, "path")

            row = layout.row()
            row.label(text="Format:")
            row.prop(self, "format", text="")

        # Armature-specific option
        if sel.asset.type == "ARMATURE":
            layout.separator()
            layout.prop(self, "export_static")

        # Bake option
        layout.prop(self, "bake_after_export")

        # Meta Objects section
        layout.separator()
        box = layout.box()
        box.label(text="Meta Objects", icon="PHYSICS")
        row = box.row()
        row.prop(self, "include_ue_colliders")

        # VotV forces colliders on
        if self.format == "votv":
            row.enabled = False
            box.label(text="VotV requires UCX_ colliders", icon="INFO")

        # Validation
        is_valid, error = validate_export_profile(
            self.target_type,
            self.path,
            self.format,
            self.bake_after_export,
            has_bake_profiles,
        )
        if not is_valid:
            box = layout.box()
            box.alert = True
            box.row().label(text=error, icon="ERROR")

        # Help text
        layout.separator()
        col = layout.column(align=True)
        col.scale_y = 0.8
        if self.target_type == "collection":
            col.label(text="• __Export__ collection will be purged", icon="INFO")
        else:
            col.label(text="• Folder path (ends with /): uses asset name", icon="INFO")
            col.label(text="• File path (.fbx): direct export, FBX only", icon="INFO")
            col.label(
                text="• File path (.obj): direct export, OBJ or VotV", icon="INFO"
            )

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        has_bake_profiles = len(cfg.bake_images) > 0

        is_valid, error = validate_export_profile(
            self.target_type,
            self.path,
            self.format,
            self.bake_after_export,
            has_bake_profiles,
        )
        if not is_valid:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        # VotV forces colliders on
        include_colliders = self.include_ue_colliders or self.format == "votv"

        profile = cfg.export_profiles[cfg.active_export_index]
        profile.target_type = self.target_type
        profile.path = self.path
        profile.format = self.format
        profile.export_static = self.export_static
        profile.bake_after_export = self.bake_after_export
        profile.include_ue_colliders = include_colliders

        tag_view3d_redraw(context)
        self.report({"INFO"}, "Updated export profile")
        return {"FINISHED"}


class NYAATOOLS_OT_RemoveExportProfile(Operator):
    """Remove the selected export profile"""

    bl_idname = "nyaatools.remove_export_profile"
    bl_label = "Remove Export Profile"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        if not sel.has_asset:
            return False
        return len(sel.asset.nyaa_asset.export_profiles) > 0

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        idx = cfg.active_export_index

        cfg.export_profiles.remove(idx)

        if (
            cfg.active_export_index >= len(cfg.export_profiles)
            and len(cfg.export_profiles) > 0
        ):
            cfg.active_export_index = len(cfg.export_profiles) - 1

        tag_view3d_redraw(context)
        self.report({"INFO"}, "Removed export profile")
        return {"FINISHED"}


class NYAATOOLS_OT_RunExportProfile(Operator):
    """Run the selected export profile"""

    bl_idname = "nyaatools.run_export_profile"
    bl_label = "Merge & Export"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        if not sel.has_asset:
            return False
        cfg = sel.asset.nyaa_asset
        if len(cfg.export_profiles) == 0:
            return False
        # Check for valid profile
        if cfg.active_export_index >= len(cfg.export_profiles):
            return False
        profile = cfg.export_profiles[cfg.active_export_index]
        # Validate bake_after_export
        if profile.bake_after_export and len(cfg.bake_images) == 0:
            return False
        # Armature assets need meshes
        if sel.asset.type == "ARMATURE":
            if len(cfg.meshes) == 0:
                return False
        # Check for layer name collisions
        if get_layer_name_collisions(sel.asset):
            return False
        return True

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        profile = cfg.export_profiles[cfg.active_export_index]

        # VotV forces colliders on
        include_colliders = profile.include_ue_colliders or profile.format == "votv"

        return bpy.ops.nyaa.avatar_merge_export(
            avatar_name=cfg.asset_name,
            export_format=profile.format,
            target_type=profile.target_type,
            export_static=profile.export_static,
            bake_after_export=profile.bake_after_export,
            include_ue_colliders=include_colliders,
        )


EXPORT_OPERATOR_CLASSES = [
    NYAATOOLS_OT_AddExportProfile,
    NYAATOOLS_OT_EditExportProfile,
    NYAATOOLS_OT_RemoveExportProfile,
    NYAATOOLS_OT_RunExportProfile,
]
