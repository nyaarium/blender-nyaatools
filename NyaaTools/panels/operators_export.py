"""
Export profile operators for NyaaTools panel.
"""

import os
import platform

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, StringProperty

from .panels_context import SelectionContext, tag_view3d_redraw
from ..asset.asset_helpers import get_layer_name_collisions


# =============================================================================
# Constants
# =============================================================================

VOTV_PRINTER_SUFFIX = "/Assets/meshes/printer/"

# Module-level pending path for VotV auto-detect button
# (dialogs can't be modified by external operators, so we use this pattern)
_pending_votv_path = None
# Stash for restoring settings when switching to/from VotV
_votv_restore_state = {}


def validate_export_profile(
    path: str,
    format: str,
) -> tuple[bool, str]:
    """
    Validate export profile configuration.
    Returns (is_valid, error_message).
    """
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

    return True, ""


def get_votv_default_path() -> str:
    """
    Get the default VotV printer export path for the current platform.
    Returns empty string if path cannot be determined.
    """
    system = platform.system()

    if system == "Windows":
        # C:\Users\{username}\AppData\Local\VotV\Assets\meshes\printer\
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            return (
                os.path.join(local_appdata, "VotV", "Assets", "meshes", "printer") + "/"
            )
    elif system == "Linux":
        # ~/.local/share/VotV/Assets/meshes/printer/
        home = os.path.expanduser("~")
        return (
            os.path.join(home, ".local", "share", "VotV", "Assets", "meshes", "printer")
            + "/"
        )

    return ""


def is_votv_printer_path(path: str) -> bool:
    """Check if path ends with VotV printer directory."""
    normalized = path.replace("\\", "/").rstrip("/") + "/"
    return normalized.endswith(VOTV_PRINTER_SUFFIX)


def update_export_path(self, context):
    """Callback for path property update. Appends / if path doesn't end with an extension."""
    if not self.path:
        return

    # Already ends with directory separator, do nothing
    if self.path.endswith("/") or self.path.endswith("\\"):
        return

    # Check if last component has a file extension
    last_component = self.path.split("/")[-1].split("\\")[-1]
    if "." in last_component:
        # Has a dot, check if it's a valid extension
        parts = last_component.split(".")
        if len(parts) > 1 and parts[-1]:
            extension = parts[-1].lower()
            # Common file extensions for export
            if extension in ("fbx", "obj"):
                return

    # No extension found, append directory separator
    self.path = self.path + "/"


def update_export_format(self, context):
    """Callback for format property update."""
    global _votv_restore_state

    if self.format == "votv":
        # Entering VotV mode: Stash current settings
        _votv_restore_state["export_static"] = self.export_static
        _votv_restore_state["include_ue_colliders"] = self.include_ue_colliders

        # Enforce VotV requirements
        self.export_static = True
        self.include_ue_colliders = True
    elif _votv_restore_state:
        # Leaving VotV mode: Restore stashed settings if available
        self.export_static = _votv_restore_state.get("export_static", False)
        self.include_ue_colliders = _votv_restore_state.get(
            "include_ue_colliders", False
        )
        _votv_restore_state.clear()


def draw_export_profile_ui(layout, operator, context, title: str):
    """
    Shared draw logic for export profile Add/Edit dialogs.

    Args:
        layout: Blender UI layout
        operator: The operator instance (has properties like target_type, path, format, etc.)
        context: Blender context
        title: Dialog title ("Export Profile" or "Edit Export Profile")
    """
    global _pending_votv_path

    # Check for pending VotV path from auto-detect button
    if _pending_votv_path:
        operator.path = _pending_votv_path
        _pending_votv_path = None

    sel = SelectionContext(context)
    cfg = sel.asset.nyaa_asset
    has_bake_profiles = len(cfg.bake_images) > 0

    layout.label(text=title, icon="EXPORT")

    # Target type selector
    layout.prop(operator, "target_type", expand=True)

    # File-specific options
    if operator.target_type == "file":
        layout.separator()
        layout.prop(operator, "path")

        row = layout.row()
        row.label(text="Format:")
        row.prop(operator, "format", text="")

        # VotV path hint
        if operator.format == "votv" and not is_votv_printer_path(operator.path):
            layout.separator()
            box = layout.box()
            box.label(text="VotV Tip:", icon="INFO")
            col = box.column(align=True)
            col.scale_y = 0.8
            col.label(text="To instantly export to game, set path to VotV's")
            col.label(text="Assets/meshes/printer/")

            votv_path = get_votv_default_path()
            if votv_path:
                row = box.row()
                row.operator(
                    "nyaatools.set_votv_path",
                    text="Auto-detect VotV Path",
                    icon="FILE_REFRESH",
                )

    # Armature-specific option
    if sel.asset.type == "ARMATURE":
        layout.separator()
        row = layout.row()
        row.prop(operator, "export_static")

        # VotV forces static export
        if operator.format == "votv":
            row.enabled = False

    # Bake option
    layout.prop(operator, "bake_after_export")

    # Meta Objects section
    layout.separator()
    box = layout.box()
    box.label(text="Meta Objects", icon="PHYSICS")

    row = box.row()
    row.prop(operator, "include_ue_colliders")
    if operator.format == "votv":
        row.enabled = False

    # Validation
    is_valid, error = validate_export_profile(
        operator.path,
        operator.format,
    )
    if not is_valid:
        box = layout.box()
        box.alert = True
        box.row().label(text=error, icon="ERROR")

    # Help text
    layout.separator()
    col = layout.column(align=True)
    col.scale_y = 0.8
    if operator.target_type == "collection":
        col.label(text="• __Export__ collection will be purged", icon="INFO")
    else:
        col.label(text="• Folder path (ends with /): uses asset name", icon="INFO")
        col.label(text="• File path (.fbx): direct export, FBX only", icon="INFO")
        col.label(text="• File path (.obj): direct export, OBJ or VotV", icon="INFO")


class NYAATOOLS_OT_SetVotvPath(Operator):
    """Set path to VotV printer directory"""

    bl_idname = "nyaatools.set_votv_path"
    bl_label = "Set VotV Path"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        global _pending_votv_path

        votv_path = get_votv_default_path()
        if not votv_path:
            self.report({"ERROR"}, "Could not detect VotV path for this platform")
            return {"CANCELLED"}

        # Set the pending path - the dialog's draw() will pick this up
        _pending_votv_path = votv_path

        # Force redraw so the dialog picks up the change
        for area in context.screen.areas:
            area.tag_redraw()

        return {"FINISHED"}


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
    path: StringProperty(
        name="Path", default="", subtype="FILE_PATH", update=update_export_path
    )
    format: EnumProperty(
        name="Format",
        items=[
            ("fbx", "FBX", "Export as FBX (Unity/Unreal)"),
            ("obj", "OBJ", "Export as OBJ (static mesh)"),
            ("votv", "VotV", "Export for Voices of the Void"),
        ],
        default="fbx",
        update=update_export_format,
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
        name="Include Unreal Engine Colliders",
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
        draw_export_profile_ui(self.layout, self, context, "Export Profile")

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset

        is_valid, error = validate_export_profile(
            self.path,
            self.format,
        )
        if not is_valid:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        # VotV forces colliders on
        include_colliders = self.include_ue_colliders or self.format == "votv"

        # VotV forces export_static on
        export_static = self.export_static or self.format == "votv"

        profile = cfg.export_profiles.add()
        profile.target_type = self.target_type
        profile.path = self.path
        profile.format = self.format
        profile.export_static = export_static
        profile.bake_after_export = self.bake_after_export
        profile.include_ue_colliders = include_colliders
        cfg.active_export_index = len(cfg.export_profiles) - 1

        tag_view3d_redraw(context)

        if self.target_type == "collection":
            self.report({"INFO"}, "Added collection export profile")
        else:
            # Auto-load VotV bake preset if creating a VotV profile
            if self.format == "votv":
                bpy.ops.nyaatools.load_bake_profile(preset="votv")
                self.report({"INFO"}, "Auto-loaded VotV bake preset")

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
    path: StringProperty(
        name="Path", default="", subtype="FILE_PATH", update=update_export_path
    )
    format: EnumProperty(
        name="Format",
        items=[
            ("fbx", "FBX", "Export as FBX (Unity/Unreal)"),
            ("obj", "OBJ", "Export as OBJ (static mesh)"),
            ("votv", "VotV", "Export for Voices of the Void"),
        ],
        default="fbx",
        update=update_export_format,
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
        name="Include Unreal Engine Colliders",
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

        # Set values before format so update callback saves correct state
        self.export_static = profile.export_static
        self.bake_after_export = profile.bake_after_export
        self.include_ue_colliders = profile.include_ue_colliders

        # Set format last to trigger update callback
        self.format = profile.format

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        draw_export_profile_ui(self.layout, self, context, "Edit Export Profile")

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset

        is_valid, error = validate_export_profile(
            self.path,
            self.format,
        )
        if not is_valid:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        profile = cfg.export_profiles[cfg.active_export_index]
        profile.target_type = self.target_type
        profile.path = self.path
        profile.format = self.format
        profile.export_static = self.export_static
        profile.bake_after_export = self.bake_after_export
        profile.include_ue_colliders = self.include_ue_colliders

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

        return bpy.ops.nyaa.asset_merge_export(
            "INVOKE_DEFAULT",
            asset_name=cfg.asset_name,
            export_format=profile.format,
            target_type=profile.target_type,
            export_static=profile.export_static,
            bake_after_export=profile.bake_after_export,
            include_ue_colliders=profile.include_ue_colliders,
        )


