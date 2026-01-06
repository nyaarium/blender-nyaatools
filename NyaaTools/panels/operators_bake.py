"""
Bake operators and helpers for NyaaTools panel.
"""

import os

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty

from .panels_context import SelectionContext
from ..common.file_stuff import sanitize_name
from ..image.texture_baker import bake_dtp_texture


# =============================================================================
# Bake Context
# =============================================================================

# Module-level storage for bake context.
# RunBake uses this to determine what meshes to bake and how to clean up.
# Set via set_pending_bake_context() or created from asset via _create_bake_context_from_asset().
_pending_bake_context = None


def set_pending_bake_context(
    meshes,
    bake_images,
    export_dir,
    on_cleanup=None,
):
    """
    Set up a bake context for the RunBake modal operator.

    This allows callers to specify exactly which meshes to bake and what
    cleanup to perform when baking completes.

    Args:
        meshes: List of mesh objects to bake from
        bake_images: CollectionProperty or list of bake image configs
        export_dir: Directory to save baked textures
        on_cleanup: Optional callback called when baking finishes (success or failure)
    """
    global _pending_bake_context
    # Copy bake image data as dicts since PropertyGroup refs may become invalid
    bake_images_data = []
    for img in bake_images:
        if isinstance(img, dict):
            bake_images_data.append(img)
        else:
            bake_images_data.append(
                {
                    "format": img.format,
                    "image_type": img.image_type,
                    "width": img.width,
                    "height": img.height,
                    "optimize_resolution": img.optimize_resolution,
                }
            )
    _pending_bake_context = {
        "meshes": meshes,
        "bake_images": bake_images_data,
        "export_dir": export_dir,
        "on_cleanup": on_cleanup,
    }


def get_pending_bake_context():
    """Get and clear the pending bake context."""
    global _pending_bake_context
    ctx = _pending_bake_context
    _pending_bake_context = None
    return ctx


def clear_pending_bake_context():
    """Clear any pending bake context without using it."""
    global _pending_bake_context
    _pending_bake_context = None


# =============================================================================
# Bake Helpers
# =============================================================================

COLOR_CHANNELS = {"cr", "cg", "cb", "er", "eg", "eb", "al"}
COLOR_ALIASES = {"rgba", "rgb", "emission"}


def is_format_color_based(dtp_format: str) -> bool:
    """Check if a DTP format string contains only color-based channels."""
    dtp_format = dtp_format.strip().lower()

    if dtp_format in COLOR_ALIASES:
        return True

    channels = dtp_format.split("-")
    for channel in channels:
        if channel not in COLOR_CHANNELS and channel not in ("0", "1", "xx"):
            return False
    return True


def get_auto_bake_settings(dtp_format: str) -> tuple:
    """Get auto-detected image type and resolution for a DTP format."""
    if is_format_color_based(dtp_format):
        return ("png", "4096", "4096")
    else:
        return ("exr", "2048", "2048")


# =============================================================================
# Bake Presets
# =============================================================================

BAKE_PRESETS = {
    "pbr_mrs": {
        "label": "PBR (MRS)",
        "description": "Standard PBR: Metallic-Specular-Roughness",
        "allow_type_change": True,
        "images": [
            ("rgba", "png", "4096", "4096"),
            ("normalgl", "exr", "2048", "2048"),
            ("me-ro-sp", "exr", "2048", "2048"),
            ("emission", "png", "4096", "4096"),
        ],
    },
    "poiyomi": {
        "label": "Poiyomi",
        "description": "Poiyomi shader: Metallic-Smoothness-1",
        "allow_type_change": True,
        "images": [
            ("rgba", "png", "4096", "4096"),
            ("normalgl", "exr", "2048", "2048"),
            ("me-sm-1", "exr", "2048", "2048"),
            ("emission", "png", "4096", "4096"),
        ],
    },
    "votv": {
        "label": "VotV",
        "description": "Voices of the Void printer format (PNG only)",
        "allow_type_change": False,
        "images": [
            ("rgba", "png", "2048", "2048"),
            ("normalgl", "png", "1024", "1024"),
            ("me-sp-ro", "png", "1024", "1024"),
            ("emission", "png", "1024", "1024"),
        ],
    },
}

BAKE_CHANNEL_ITEMS_RGB = [
    ("0", "0 (Black)", "Constant 0.0"),
    ("1", "1 (White)", "Constant 1.0"),
    (None, "─── Color ───", ""),
    ("cr", "Base Color R", "sRGB base color red"),
    ("cg", "Base Color G", "sRGB base color green"),
    ("cb", "Base Color B", "sRGB base color blue"),
    ("al", "Alpha", "Alpha/opacity channel"),
    (None, "─── PBR ───", ""),
    ("me", "Metallic", "Metallic value"),
    ("sp", "Specular", "Specular value"),
    ("ro", "Roughness", "Roughness value"),
    ("sm", "Smoothness", "Smoothness (inverted roughness)"),
    ("ao", "Ambient Occlusion", "AO value"),
    (None, "─── Normal ───", ""),
    ("nx", "Normal X", "Normal map X component"),
    ("ng", "Normal +Y (OpenGL)", "Normal map Y (OpenGL convention)"),
    ("nd", "Normal -Y (DirectX)", "Normal map Y (DirectX convention)"),
    ("he", "Height", "Height/displacement value"),
    (None, "─── Emission ───", ""),
    ("er", "Emission R", "Emission red"),
    ("eg", "Emission G", "Emission green"),
    ("eb", "Emission B", "Emission blue"),
    ("es", "Emission Strength", "Emission strength multiplier"),
]

BAKE_CHANNEL_ITEMS_ALPHA = [
    ("xx", "Unused (RGB only)", "Omit alpha channel, output RGB image"),
] + BAKE_CHANNEL_ITEMS_RGB

BAKE_CHANNEL_ENUM_RGB = [
    (item[0], item[1], item[2])
    for item in BAKE_CHANNEL_ITEMS_RGB
    if item[0] is not None
]

BAKE_CHANNEL_ENUM_ALPHA = [
    (item[0], item[1], item[2])
    for item in BAKE_CHANNEL_ITEMS_ALPHA
    if item[0] is not None
]

BAKE_TEMPLATE_ITEMS = [
    ("rgba", "RGBA (Base Color + Alpha)", "Full base color with alpha"),
    ("rgb", "RGB (Base Color)", "Base color without alpha"),
    ("normalgl", "Normal (OpenGL)", "Normal map in OpenGL format"),
    ("normaldx", "Normal (DirectX)", "Normal map in DirectX format"),
    ("emission", "Emission", "Emissive RGB channels"),
    ("custom", "Custom...", "Configure individual R, G, B, A channels"),
]


# =============================================================================
# Bake Operators
# =============================================================================


class NYAATOOLS_OT_LoadBakeProfile(Operator):
    """Load a predefined bake profile"""

    bl_idname = "nyaatools.load_bake_profile"
    bl_label = "Load Preset"
    bl_options = {"REGISTER", "UNDO"}

    preset: EnumProperty(
        name="Preset",
        items=[
            ("pbr_mrs", "PBR (MRS)", "Standard PBR: Metallic-Roughness-Specular"),
            ("poiyomi", "Poiyomi", "Poiyomi shader: Metallic-Smoothness-1"),
            ("votv", "VotV", "Voices of the Void printer format (PNG only)"),
        ],
        default="pbr_mrs",
    )

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        return sel.has_asset

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select a bake profile:", icon="PRESET")

        col = layout.column(align=True)
        for key in BAKE_PRESETS:
            col.row().prop_enum(self, "preset", key)

        layout.separator()
        preset_data = BAKE_PRESETS.get(self.preset, {})
        if preset_data:
            box = layout.box()
            box.label(text="Images:", icon="IMAGE_DATA")
            for fmt, img_type, w, h in preset_data.get("images", []):
                box.row().label(text=f"  {fmt} ({img_type.upper()}, {w}x{h})")

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset

        preset_data = BAKE_PRESETS.get(self.preset)
        if not preset_data:
            self.report({"ERROR"}, f"Unknown preset: {self.preset}")
            return {"CANCELLED"}

        cfg.bake_images.clear()
        for fmt, img_type, w, h in preset_data["images"]:
            img = cfg.bake_images.add()
            img.format = fmt
            img.image_type = img_type
            img.width = w
            img.height = h

        for area in context.screen.areas:
            area.tag_redraw()

        self.report({"INFO"}, f"Loaded bake profile: {preset_data['label']}")
        return {"FINISHED"}


class NYAATOOLS_OT_AddBakeImage(Operator):
    """Add a new bake image configuration"""

    bl_idname = "nyaatools.add_bake_image"
    bl_label = "Custom Bake"
    bl_options = {"REGISTER", "UNDO"}

    template: EnumProperty(name="Template", items=BAKE_TEMPLATE_ITEMS, default="rgba")
    r_channel: EnumProperty(name="R", items=BAKE_CHANNEL_ENUM_RGB, default="me")
    g_channel: EnumProperty(name="G", items=BAKE_CHANNEL_ENUM_RGB, default="ro")
    b_channel: EnumProperty(name="B", items=BAKE_CHANNEL_ENUM_RGB, default="sp")
    a_channel: EnumProperty(name="A", items=BAKE_CHANNEL_ENUM_ALPHA, default="xx")
    image_type: EnumProperty(
        name="Type",
        items=[
            ("png", "PNG", "8-bit PNG (good for color/diffuse)"),
            ("exr", "EXR", "32-bit EXR (best for linear/utility maps)"),
        ],
        default="png",
    )
    width: EnumProperty(
        name="Width",
        items=[
            ("16384", "16384", ""),
            ("8192", "8192", ""),
            ("4096", "4096", ""),
            ("2048", "2048", ""),
            ("1024", "1024", ""),
            ("512", "512", ""),
            ("256", "256", ""),
            ("128", "128", ""),
            ("64", "64", ""),
        ],
        default="4096",
    )
    height: EnumProperty(
        name="Height",
        items=[
            ("16384", "16384", ""),
            ("8192", "8192", ""),
            ("4096", "4096", ""),
            ("2048", "2048", ""),
            ("1024", "1024", ""),
            ("512", "512", ""),
            ("256", "256", ""),
            ("128", "128", ""),
            ("64", "64", ""),
        ],
        default="4096",
    )
    optimize_resolution: BoolProperty(
        name="Optimize",
        default=True,
        description="Auto-detect optimal resolution (use width/height as maximum cap)",
    )

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        return sel.has_asset

    def invoke(self, context, event):
        img_type, w, h = get_auto_bake_settings(self.template)
        self.image_type = img_type
        self.width = w
        self.height = h
        return context.window_manager.invoke_props_dialog(self, width=300)

    def _get_current_format(self) -> str:
        if self.template == "custom":
            channels = [self.r_channel, self.g_channel, self.b_channel]
            if self.a_channel != "xx":
                channels.append(self.a_channel)
            return "-".join(channels)
        return self.template

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "template")

        if self.template == "custom":
            layout.separator()
            box = layout.box()
            box.label(text="Custom Channels:", icon="COLOR")
            col = box.column(align=True)
            col.prop(self, "r_channel")
            col.prop(self, "g_channel")
            col.prop(self, "b_channel")
            col.prop(self, "a_channel")

        layout.separator()
        layout.prop(self, "image_type")

        fmt = self._get_current_format()
        if self.image_type == "png" and not is_format_color_based(fmt):
            box = layout.box()
            box.alert = True
            box.label(text="Warning: PNG may lose precision", icon="ERROR")
            box.label(text="For linear/utility maps, EXR recommended.")

        layout.separator()
        row = layout.row(align=True)
        row.prop(self, "width")
        row.prop(self, "height")

        layout.prop(self, "optimize_resolution")

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset

        fmt = self._get_current_format()

        img = cfg.bake_images.add()
        img.format = fmt
        img.image_type = self.image_type
        img.width = self.width
        img.height = self.height
        img.optimize_resolution = self.optimize_resolution

        cfg.active_bake_index = len(cfg.bake_images) - 1

        self.report({"INFO"}, f"Added bake image: {fmt} ({self.image_type.upper()})")
        return {"FINISHED"}


class NYAATOOLS_OT_EditBakeImage(Operator):
    """Edit the selected bake image configuration"""

    bl_idname = "nyaatools.edit_bake_image"
    bl_label = "Edit Bake Image"
    bl_options = {"REGISTER", "UNDO"}

    template: EnumProperty(name="Template", items=BAKE_TEMPLATE_ITEMS, default="custom")
    r_channel: EnumProperty(name="R", items=BAKE_CHANNEL_ENUM_RGB, default="me")
    g_channel: EnumProperty(name="G", items=BAKE_CHANNEL_ENUM_RGB, default="ro")
    b_channel: EnumProperty(name="B", items=BAKE_CHANNEL_ENUM_RGB, default="sp")
    a_channel: EnumProperty(name="A", items=BAKE_CHANNEL_ENUM_ALPHA, default="xx")
    image_type: EnumProperty(
        name="Type",
        items=[
            ("png", "PNG", "8-bit PNG (good for color/diffuse)"),
            ("exr", "EXR", "32-bit EXR (best for linear/utility maps)"),
        ],
        default="png",
    )
    width: EnumProperty(
        name="Width",
        items=[
            ("16384", "16384", ""),
            ("8192", "8192", ""),
            ("4096", "4096", ""),
            ("2048", "2048", ""),
            ("1024", "1024", ""),
            ("512", "512", ""),
            ("256", "256", ""),
            ("128", "128", ""),
            ("64", "64", ""),
        ],
        default="4096",
    )
    height: EnumProperty(
        name="Height",
        items=[
            ("16384", "16384", ""),
            ("8192", "8192", ""),
            ("4096", "4096", ""),
            ("2048", "2048", ""),
            ("1024", "1024", ""),
            ("512", "512", ""),
            ("256", "256", ""),
            ("128", "128", ""),
            ("64", "64", ""),
        ],
        default="4096",
    )
    optimize_resolution: BoolProperty(
        name="Optimize",
        default=True,
        description="Auto-detect optimal resolution (use width/height as maximum cap)",
    )

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        if not sel.has_asset:
            return False
        return len(sel.asset.nyaa_asset.bake_images) > 0

    def invoke(self, context, event):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        img = cfg.bake_images[cfg.active_bake_index]

        fmt = img.format
        self.image_type = img.image_type
        self.width = img.width
        self.height = img.height
        self.optimize_resolution = img.optimize_resolution

        known_aliases = ["rgba", "rgb", "normalgl", "normaldx", "emission"]
        if fmt in known_aliases:
            self.template = fmt
        else:
            self.template = "custom"
            parts = fmt.split("-")
            self.r_channel = parts[0] if len(parts) > 0 else "0"
            self.g_channel = parts[1] if len(parts) > 1 else "0"
            self.b_channel = parts[2] if len(parts) > 2 else "0"
            self.a_channel = parts[3] if len(parts) > 3 else "xx"

        return context.window_manager.invoke_props_dialog(self, width=300)

    def _get_current_format(self) -> str:
        if self.template == "custom":
            channels = [self.r_channel, self.g_channel, self.b_channel]
            if self.a_channel != "xx":
                channels.append(self.a_channel)
            return "-".join(channels)
        return self.template

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "template")

        if self.template == "custom":
            layout.separator()
            box = layout.box()
            box.label(text="Custom Channels:", icon="COLOR")
            col = box.column(align=True)
            col.prop(self, "r_channel")
            col.prop(self, "g_channel")
            col.prop(self, "b_channel")
            col.prop(self, "a_channel")

        layout.separator()
        layout.prop(self, "image_type")

        fmt = self._get_current_format()
        if self.image_type == "png" and not is_format_color_based(fmt):
            box = layout.box()
            box.alert = True
            box.label(text="Warning: PNG may lose precision", icon="ERROR")
            box.label(text="For linear/utility maps, EXR recommended.")

        layout.separator()
        row = layout.row(align=True)
        row.prop(self, "width")
        row.label(text="x")
        row.prop(self, "height")

        layout.prop(self, "optimize_resolution")

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        img = cfg.bake_images[cfg.active_bake_index]

        fmt = self._get_current_format()

        img.format = fmt
        img.image_type = self.image_type
        img.width = self.width
        img.height = self.height
        img.optimize_resolution = self.optimize_resolution

        self.report({"INFO"}, f"Updated bake image: {fmt} ({self.image_type.upper()})")
        return {"FINISHED"}


class NYAATOOLS_OT_RemoveBakeImage(Operator):
    """Remove the selected bake image configuration"""

    bl_idname = "nyaatools.remove_bake_image"
    bl_label = "Remove Bake Image"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        if not sel.has_asset:
            return False
        return len(sel.asset.nyaa_asset.bake_images) > 0

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        idx = cfg.active_bake_index

        name = cfg.bake_images[idx].format
        cfg.bake_images.remove(idx)

        if cfg.active_bake_index >= len(cfg.bake_images) and len(cfg.bake_images) > 0:
            cfg.active_bake_index = len(cfg.bake_images) - 1

        self.report({"INFO"}, f"Removed bake image: {name}")
        return {"FINISHED"}


class NYAATOOLS_OT_RunBake(Operator):
    """Bake all configured images for all materials on asset meshes"""

    bl_idname = "nyaatools.run_bake"
    bl_label = "Bake All Materials"
    bl_options = {"REGISTER"}

    # Modal state
    _timer = None
    _overlay = None
    _eta = None
    _tasks = []  # List of task dicts
    _task_index = 0
    _export_dir = ""
    _baked_count = 0
    _failed_count = 0
    _materials_completed = 0
    _current_material = ""
    _awaiting_confirmation = False  # True when waiting for user to press ENTER
    _pending_bake = False  # True when we've shown "baking..." but haven't started yet
    _task_start_time = 0.0  # Start time of current task
    # Cleanup callback (called when baking finishes)
    _on_cleanup = None

    @classmethod
    def poll(cls, context):
        # Only allow if there's a pending bake context (from merge/export)
        return _pending_bake_context is not None

    def invoke(self, context, event):
        from ..ui.progress_overlay import ProgressOverlay, BakeTask
        from ..ui.eta_estimator import (
            ETAEstimator,
            resolution_to_megapixels,
            is_rgba_format,
        )

        # Get pending bake context (set by merge/export)
        pending_ctx = get_pending_bake_context()
        if not pending_ctx:
            self.report({"ERROR"}, "No pending bake context")
            return {"CANCELLED"}

        # Extract context data
        meshes = pending_ctx["meshes"]
        bake_images = pending_ctx["bake_images"]
        self._export_dir = pending_ctx["export_dir"]
        self._on_cleanup = pending_ctx.get("on_cleanup")

        # Filter out UCX_ collision meshes (safety check)
        meshes = [m for m in meshes if not m.name.upper().startswith("UCX_")]

        print(f"[RunBake] Baking {len(meshes)} meshes")

        if not meshes:
            self.report({"ERROR"}, "No meshes to bake")
            return {"CANCELLED"}

        os.makedirs(self._export_dir, exist_ok=True)

        print(f"[RunBake] Export directory: {self._export_dir}")
        print(f"[RunBake] Meshes to bake: {[m.name for m in meshes]}")

        # Collect all materials and build task list
        materials_seen = set()
        material_mesh_map = {}  # mat_name -> mesh

        for mesh in meshes:
            if not mesh.data or not mesh.data.materials:
                print(f"[RunBake] Mesh '{mesh.name}' has no materials, skipping")
                continue
            for mat in mesh.data.materials:
                if mat and mat.name not in materials_seen:
                    materials_seen.add(mat.name)
                    material_mesh_map[mat.name] = (mesh, mat)
                    print(
                        f"[RunBake] Found material '{mat.name}' on mesh '{mesh.name}'"
                    )

        if not material_mesh_map:
            self.report({"ERROR"}, "No materials found on meshes")
            return {"CANCELLED"}

        # Build task list and overlay display data
        self._tasks = []
        tasks_by_material = {}
        task_idx = 0

        for mat_name, (mesh, mat) in material_mesh_map.items():
            tasks_by_material[mat_name] = []

            for bake_img in bake_images:
                # Handle both dict (from pending context) and PropertyGroup access
                if isinstance(bake_img, dict):
                    dtp_format = bake_img["format"]
                    width = int(bake_img["width"])
                    height = int(bake_img["height"])
                    img_type = bake_img["image_type"]
                    optimize = bake_img["optimize_resolution"]
                else:
                    dtp_format = bake_img.format
                    width = int(bake_img.width)
                    height = int(bake_img.height)
                    img_type = bake_img.image_type
                    optimize = bake_img.optimize_resolution

                # Create display task
                res_str = f"{width}x{height}"
                display_task = BakeTask(
                    material_name=mat_name,
                    dtp_format=dtp_format,
                    image_type=img_type,
                    resolution=res_str,
                    optimize=optimize,
                )
                tasks_by_material[mat_name].append(display_task)

                # Determine bake type for ETA estimation
                is_rgba = is_rgba_format(dtp_format)
                bake_type = "bake_rgba" if is_rgba else "bake_rgb"

                # Create work task - store extracted values instead of bake_img reference
                self._tasks.append(
                    {
                        "mesh": mesh,
                        "mat": mat,
                        "dtp_format": dtp_format,
                        "width": width,
                        "height": height,
                        "img_type": img_type,
                        "optimize": optimize,
                        "display_task": display_task,
                        "megapixels": resolution_to_megapixels(width, height),
                        "bake_type": bake_type,
                    }
                )
                task_idx += 1

        print(f"[RunBake] Total bake tasks: {len(self._tasks)}")

        # Ensure object mode
        if context.active_object and context.active_object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        # Initialize state
        self._task_index = 0
        self._baked_count = 0
        self._failed_count = 0
        self._materials_completed = 0
        self._current_material = ""
        self._awaiting_confirmation = False
        self._pending_bake = False

        # Initialize overlay
        self._overlay = ProgressOverlay()
        self._overlay.start(context, "Baking Textures", tasks_by_material)

        # Initialize ETA estimator
        self._eta = ETAEstimator(context)

        # Calculate individual ETAs for each task (if calibrated)
        initial_eta = ""
        if self._eta.is_calibrated and self._tasks:
            total_eta = 0.0
            for task in self._tasks:
                task_eta = self._eta.estimate_task_time(
                    task["bake_type"], task["megapixels"]
                )
                task["display_task"].estimated_seconds = task_eta
                total_eta += task_eta
            initial_eta = self._eta.format_eta(total_eta)

        # Set initial message and ETA (update_progress also triggers redraw)
        self._overlay._current_message = "Starting..."
        self._overlay.update_progress(0, len(self._tasks), initial_eta)

        # Start timer for modal updates
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)

        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        # Handle confirmation state - wait for ENTER to close
        if self._awaiting_confirmation:
            if event.type in ("RET", "NUMPAD_ENTER") and event.value == "PRESS":
                was_cancelled = self._overlay and self._overlay.state == "cancelled"

                result_msg = f"Baked {self._baked_count} textures"
                if self._failed_count > 0:
                    result_msg += f", {self._failed_count} failed"
                result_msg += f". Output: {self._export_dir}"

                self._cleanup(context)

                if was_cancelled:
                    self.report({"WARNING"}, f"Cancelled. {result_msg}")
                    return {"CANCELLED"}
                elif self._failed_count > 0:
                    self.report({"WARNING"}, result_msg)
                else:
                    self.report({"INFO"}, result_msg)
                return {"FINISHED"}

            # Block all other input while awaiting confirmation
            return {"RUNNING_MODAL"}

        # Handle ESC to cancel (only works between bakes)
        if event.type == "ESC" and event.value == "PRESS":
            self._overlay.set_cancelled(
                f"Cancelled. {self._baked_count} completed, {len(self._tasks) - self._task_index} remaining."
            )
            self._awaiting_confirmation = True
            # Remove timer since we're done processing
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None
            return {"RUNNING_MODAL"}

        if event.type == "TIMER":
            # Check if we're done
            if self._task_index >= len(self._tasks):
                # Show completion state and wait for confirmation
                if self._failed_count > 0:
                    self._overlay.set_completed(
                        f"Completed with {self._failed_count} failures. {self._baked_count} textures saved."
                    )
                else:
                    self._overlay.set_completed(
                        f"Successfully baked {self._baked_count} textures!"
                    )
                self._awaiting_confirmation = True
                # Remove timer since we're done processing
                if self._timer:
                    context.window_manager.event_timer_remove(self._timer)
                    self._timer = None
                return {"RUNNING_MODAL"}

            # Get current task
            task = self._tasks[self._task_index]
            mesh = task["mesh"]
            mat = task["mat"]
            megapixels = task["megapixels"]
            bake_type = task["bake_type"]
            dtp_format = task["dtp_format"]

            # Phase 1: Update overlay to show we're about to bake, then return
            # This gives the viewport time to redraw before the blocking bake
            if not self._pending_bake:
                # Track material changes for ETA
                if mat.name != self._current_material:
                    if self._current_material:
                        self._materials_completed += 1
                    self._current_material = mat.name

                # Update overlay - mark task as active
                self._overlay.set_active_task(self._task_index)

                self._pending_bake = True
                return {"RUNNING_MODAL"}

            # Phase 2: Actually perform the bake
            self._pending_bake = False

            # Ensure mesh is accessible (unhide collections it belongs to)
            _ensure_object_accessible(mesh)

            # Select and activate the mesh
            bpy.ops.object.select_all(action="DESELECT")
            mesh.select_set(True)
            context.view_layer.objects.active = mesh

            # Start timing
            import time

            self._task_start_time = time.perf_counter()
            self._eta.start_task(bake_type, megapixels)

            # Perform the bake with error handling
            width = task["width"]
            height = task["height"]
            img_type = task["img_type"]
            optimize = task["optimize"]

            try:
                result_image = bake_dtp_texture(
                    dtp_format,
                    mesh,
                    mat,
                    resolution=None if optimize else (width, height),
                    max_resolution=(width, height) if optimize else None,
                )
            except Exception as e:
                print(f"[RunBake] ERROR baking {dtp_format}: {e}")
                import traceback

                traceback.print_exc()
                result_image = None
                self._overlay.set_error(f"Bake failed: {str(e)[:50]}")
                self._awaiting_confirmation = True
                if self._timer:
                    context.window_manager.event_timer_remove(self._timer)
                    self._timer = None
                return {"RUNNING_MODAL"}

            # End timing
            elapsed = time.perf_counter() - self._task_start_time
            self._eta.end_task()

            # Process result
            if result_image:
                mat_name = sanitize_name(mat.name)
                ext = "exr" if img_type == "exr" else "png"
                filename = f"{mat_name}.{dtp_format}.{ext}"
                save_path = os.path.join(self._export_dir, filename)

                # Get resolution before saving (image is removed after save)
                result_w = result_image.size[0]
                result_h = result_image.size[1]

                if _save_baked_image(result_image, save_path, img_type):
                    self._baked_count += 1
                    result_res = f"{result_w}x{result_h}"
                    self._overlay.mark_task_done(
                        self._task_index, result_res=result_res, elapsed_seconds=elapsed
                    )
                else:
                    self._failed_count += 1
                    self._overlay.mark_task_done(
                        self._task_index, result_res="FAILED", elapsed_seconds=elapsed
                    )
            else:
                self._failed_count += 1
                self._overlay.mark_task_done(
                    self._task_index, result_res="FAILED", elapsed_seconds=elapsed
                )

            # Recalculate ETAs for remaining pending tasks (scalars may have updated)
            for remaining_task in self._tasks[self._task_index + 1 :]:
                new_eta = self._eta.estimate_task_time(
                    remaining_task["bake_type"], remaining_task["megapixels"]
                )
                remaining_task["display_task"].estimated_seconds = new_eta

            # Calculate total ETA for remaining tasks
            eta_str = ""
            if self._eta.is_calibrated:
                remaining_tasks = [
                    (t["bake_type"], t["megapixels"])
                    for t in self._tasks[self._task_index + 1 :]
                ]
                if remaining_tasks:
                    eta_seconds = self._eta.estimate_remaining(remaining_tasks)
                    eta_str = self._eta.format_eta(eta_seconds)

            # Update progress
            self._overlay.update_progress(
                self._task_index + 1, len(self._tasks), eta_str
            )

            self._task_index += 1

        return {"RUNNING_MODAL"}

    def _cleanup(self, context):
        """Clean up timer, overlay, and call cleanup callback."""
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

        if self._overlay:
            self._overlay.finish()
            self._overlay = None

        # Call cleanup callback (handles temp scene, collection hiding, etc.)
        if self._on_cleanup:
            try:
                self._on_cleanup()
                print("[RunBake] Cleanup callback executed")
            except Exception as e:
                print(f"[RunBake] Cleanup callback error: {e}")
            self._on_cleanup = None

        self._eta = None
        self._tasks = []


def _ensure_object_accessible(obj):
    """
    Ensure an object is accessible for selection and baking.

    Unhides the object and any collections it belongs to, both for viewport and render.
    """
    if not obj:
        return

    # Unhide the object itself (viewport and render)
    obj.hide_viewport = False
    obj.hide_render = False
    obj.hide_set(False)

    # Unhide collections the object belongs to
    view_layer = bpy.context.view_layer
    for collection in obj.users_collection:
        collection.hide_viewport = False
        collection.hide_render = False

        # Also unhide in view layer
        layer_collection = _find_layer_collection(
            view_layer.layer_collection, collection.name
        )
        if layer_collection:
            layer_collection.exclude = False
            layer_collection.hide_viewport = False


def _find_layer_collection(layer_collection, name):
    """Recursively find a LayerCollection by name."""
    if layer_collection.name == name:
        return layer_collection
    for child in layer_collection.children:
        found = _find_layer_collection(child, name)
        if found:
            return found
    return None


def _save_baked_image(image, output_path, img_type):
    """Save a baked image and clean up from memory."""
    if not image:
        return False

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        image.filepath_raw = output_path
        if img_type == "exr":
            image.file_format = "OPEN_EXR"
        else:
            image.file_format = "PNG"
        image.save()

        bpy.data.images.remove(image)
        return True
    except Exception as e:
        print(f"Failed to save baked image to {output_path}: {e}")
        if image and image.name in bpy.data.images:
            bpy.data.images.remove(image)
        return False


BAKE_OPERATOR_CLASSES = [
    NYAATOOLS_OT_LoadBakeProfile,
    NYAATOOLS_OT_AddBakeImage,
    NYAATOOLS_OT_EditBakeImage,
    NYAATOOLS_OT_RemoveBakeImage,
    NYAATOOLS_OT_RunBake,
]
