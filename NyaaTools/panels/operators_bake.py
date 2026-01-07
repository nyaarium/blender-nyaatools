"""
Bake operators and helpers for NyaaTools panel.
"""

import os
from typing import Tuple

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty

from .panels_context import SelectionContext
from ..common.file_stuff import sanitize_name
from ..image.texture_baker import (
    bake_dtp_texture,
    _parse_format_string,
    _get_bake_type_for_channels,
    DTP_SOCKET_MAP,
)
from ..image.material_analyzer import find_principled_bsdf, detect_best_resolution
from ..bake.bake_context import (
    get_pending_bake_context as get_bake_context,
    BakeContext,
)
from ..bake.bake_prepare import prepare_meshes_for_baking
from ..bake.bake_execute import execute_bake_for_material


# =============================================================================
# Bake Context (DEPRECATED - use bake.bake_context instead)
# =============================================================================

# Legacy compatibility: Re-export set_pending_bake_context from bake_context
# This allows old code to continue working during transition
from ..bake.bake_context import (
    set_pending_bake_context,
    get_pending_bake_context,
    clear_pending_bake_context,
    has_pending_bake_context,
)


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
# Helper Functions
# =============================================================================


def _detect_render_resolution(
    material: bpy.types.Material,
    dtp_format: str,
    max_resolution: Tuple[int, int],
) -> Tuple[int, int]:
    """
    Detect the render resolution for a material based on its shader graph.

    Args:
        material: The material to analyze
        dtp_format: DTP format string (e.g., "rgba", "normalgl", "me-sp-ro")
        max_resolution: Maximum resolution cap (width, height)

    Returns:
        Tuple of (width, height) for the detected render resolution
    """
    if not material or not material.use_nodes:
        return max_resolution

    # Find Principled BSDF
    principled_result = find_principled_bsdf(material)
    if not principled_result:
        return max_resolution

    principled_bsdf = principled_result["principled_bsdf"]
    tree_stack = principled_result["tree_stack"]

    # Parse format to determine bake type
    try:
        channels = _parse_format_string(dtp_format)
        bake_type = _get_bake_type_for_channels(channels)
    except (ValueError, AttributeError):
        # If parsing fails, default to max resolution
        return max_resolution

    detected_resolution = None

    if bake_type == "NORMAL":
        # For normal maps, detect from Normal socket
        normal_socket = principled_bsdf.inputs.get("Normal")
        if normal_socket and normal_socket.is_linked:
            detected_resolution = detect_best_resolution(normal_socket, tree_stack)
        else:
            detected_resolution = (1024, 1024)  # Default for unconnected normal
    else:
        # For emission bakes, check relevant sockets
        # Check Base Color and Emission Color sockets
        resolutions = []

        base_color_socket = principled_bsdf.inputs.get("Base Color")
        if base_color_socket and base_color_socket.is_linked:
            resolutions.append(detect_best_resolution(base_color_socket, tree_stack))

        emission_color_socket = principled_bsdf.inputs.get("Emission Color")
        if emission_color_socket and emission_color_socket.is_linked:
            resolutions.append(
                detect_best_resolution(emission_color_socket, tree_stack)
            )

        # Also check other sockets that might be used (Metallic, Roughness, etc.)
        # based on the channels in the format
        for channel in channels:
            socket_mapping = DTP_SOCKET_MAP.get(channel)
            if isinstance(socket_mapping, str) and socket_mapping not in (
                "__CONSTANT_0__",
                "__CONSTANT_1__",
                "__UNUSED__",
            ):
                socket = principled_bsdf.inputs.get(socket_mapping)
                if socket and socket.is_linked:
                    resolutions.append(detect_best_resolution(socket, tree_stack))
            elif isinstance(socket_mapping, tuple):
                socket_name, _ = socket_mapping
                socket = principled_bsdf.inputs.get(socket_name)
                if socket and socket.is_linked:
                    resolutions.append(detect_best_resolution(socket, tree_stack))

        if resolutions:
            # Take max of all detected resolutions
            detected_resolution = (
                max(r[0] for r in resolutions),
                max(r[1] for r in resolutions),
            )
        else:
            detected_resolution = (512, 512)  # Default if nothing connected

    # Apply max_resolution cap
    if detected_resolution:
        max_width, max_height = max_resolution
        final_resolution = (
            min(detected_resolution[0], max_width),
            min(detected_resolution[1], max_height),
        )
        return final_resolution

    return max_resolution


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
# Bake Image Dialog Helpers
# =============================================================================


def get_bake_format_from_operator(operator) -> str:
    """
    Get the DTP format string from a bake image operator's properties.

    Args:
        operator: The operator instance with template/channel properties

    Returns:
        DTP format string like "rgba", "normalgl", or "me-ro-sp"
    """
    if operator.template == "custom":
        channels = [operator.r_channel, operator.g_channel, operator.b_channel]
        if operator.a_channel != "xx":
            channels.append(operator.a_channel)
        return "-".join(channels)
    return operator.template


def draw_bake_image_ui(layout, operator, context):
    """
    Shared draw logic for bake image Add/Edit dialogs.

    Args:
        layout: Blender UI layout
        operator: The operator instance (has properties like template, channels, etc.)
        context: Blender context
    """
    layout.prop(operator, "template")

    if operator.template == "custom":
        layout.separator()
        box = layout.box()
        box.label(text="Custom Channels:", icon="COLOR")
        col = box.column(align=True)
        col.prop(operator, "r_channel")
        col.prop(operator, "g_channel")
        col.prop(operator, "b_channel")
        col.prop(operator, "a_channel")

    layout.separator()
    layout.prop(operator, "image_type")

    fmt = get_bake_format_from_operator(operator)
    if operator.image_type == "png" and not is_format_color_based(fmt):
        box = layout.box()
        box.alert = True
        box.label(text="Warning: PNG may lose precision", icon="ERROR")
        box.label(text="For linear/utility maps, EXR recommended.")

    layout.separator()
    row = layout.row(align=True)
    row.prop(operator, "width")
    row.label(text="x")
    row.prop(operator, "height")

    layout.prop(operator, "optimize_resolution")


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
    bl_label = "Add Bake Channel"
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

    def draw(self, context):
        draw_bake_image_ui(self.layout, self, context)

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset

        fmt = get_bake_format_from_operator(self)

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
    bl_label = "Edit Bake Channel"
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

    def draw(self, context):
        draw_bake_image_ui(self.layout, self, context)

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        img = cfg.bake_images[cfg.active_bake_index]

        fmt = get_bake_format_from_operator(self)

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
    bl_label = "Remove Bake Channel"
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


class NYAATOOLS_OT_StartBakeQueue(Operator):
    """Start the polling process to bake the images in the queue"""

    bl_idname = "nyaatools.start_bake_queue"
    bl_label = "Start Bake Queue"
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
    # Bake context
    _bake_ctx = None
    _wait_for_enter = False
    _awaiting_enter = False  # True when waiting for Enter key before bake

    @classmethod
    def poll(cls, context):
        # Only allow if there's a pending bake context (from merge/export)
        return has_pending_bake_context()

    def invoke(self, context, event):
        from ..ui.progress_overlay import ProgressOverlay, BakeTask
        from ..ui.eta_estimator import (
            ETAEstimator,
            resolution_to_megapixels,
            is_rgba_format,
        )

        # Get pending bake context (set by merge/export)
        ctx = get_bake_context()
        if not ctx:
            self.report({"ERROR"}, "No pending bake context")
            return {"CANCELLED"}

        if not isinstance(ctx, BakeContext):
            # Legacy dict format - convert to BakeContext for compatibility
            self.report({"ERROR"}, "Legacy bake context format not supported. Please update caller.")
            return {"CANCELLED"}

        # Store context reference
        self._bake_ctx = ctx
        self._export_dir = ctx.export_dir
        self._on_cleanup = ctx.on_cleanup
        self._filename_formatter = ctx.filename_formatter
        self._wait_for_enter = ctx.wait_for_enter

        print(f"[RunBake] Starting bake with {len(ctx.mesh_metas)} mesh metas")

        # Run prepare phase (steps 1-5): delete colliders, apply modifiers, separate by material, join compatible meshes
        print("[RunBake] Preparing meshes for baking...")
        try:
            meshes_by_material = prepare_meshes_for_baking(ctx, debug_print=print)
        except Exception as e:
            # Cleanup on failure
            print(f"[RunBake] Prepare failed: {e}")
            if self._on_cleanup:
                try:
                    self._on_cleanup()
                    print("[RunBake] Cleanup callback executed after prepare failure")
                except Exception as cleanup_error:
                    print(f"[RunBake] Cleanup callback error: {cleanup_error}")
            self.report({"ERROR"}, f"Prepare failed: {str(e)}")
            return {"CANCELLED"}

        if not meshes_by_material:
            # Cleanup if no materials found
            if self._on_cleanup:
                try:
                    self._on_cleanup()
                    print("[RunBake] Cleanup callback executed (no materials)")
                except Exception as cleanup_error:
                    print(f"[RunBake] Cleanup callback error: {cleanup_error}")
            self.report({"ERROR"}, "No materials found after preparation")
            return {"CANCELLED"}

        os.makedirs(self._export_dir, exist_ok=True)

        print(f"[RunBake] Export directory: {self._export_dir}")
        print(f"[RunBake] Materials to bake: {list(meshes_by_material.keys())}")

        # Build task list and overlay display data from meshes_by_material
        self._tasks = []
        tasks_by_material = {}

        for mat_name, meshes in meshes_by_material.items():
            tasks_by_material[mat_name] = []

            # Get material object
            material = bpy.data.materials.get(mat_name)
            if not material:
                print(f"[RunBake] Material '{mat_name}' not found, skipping")
                continue

            # Calculate ETA multiplier for multi-mesh materials
            mesh_count = len(meshes)
            format_count = len(ctx.bake_images)

            for bake_img in ctx.bake_images:
                # Extract bake image config (already converted to BakeImageConfig)
                dtp_format = bake_img.format
                width = int(bake_img.width)
                height = int(bake_img.height)
                img_type = bake_img.image_type
                optimize = bake_img.optimize_resolution

                # Create display task
                res_str = f"{width}x{height}"

                # Detect render resolution if optimize is enabled
                render_width, render_height = width, height
                if optimize and material:
                    try:
                        detected = _detect_render_resolution(
                            material, dtp_format, (width, height)
                        )
                        render_width, render_height = detected
                    except Exception as e:
                        print(
                            f"[RunBake] Failed to detect render resolution for {mat_name}: {e}"
                        )
                        # Fall back to max resolution
                        render_width, render_height = width, height
                else:
                    # If not optimizing, render resolution equals max resolution
                    render_width, render_height = width, height

                render_res_str = f"{render_width}x{render_height}"

                display_task = BakeTask(
                    material_name=mat_name,
                    dtp_format=dtp_format,
                    image_type=img_type,
                    resolution=res_str,
                    optimize=optimize,
                )
                display_task.render_resolution = render_res_str
                tasks_by_material[mat_name].append(display_task)

                # Determine bake type for ETA estimation
                is_rgba = is_rgba_format(dtp_format)
                bake_type = "bake_rgba" if is_rgba else "bake_rgb"

                # Create work task - store material name and meshes list
                # Use render resolution for ETA calculation
                megapixels = resolution_to_megapixels(render_width, render_height)
                
                # For multi-mesh materials, multiply ETA by (mesh_count × format_count)
                # This accounts for individual mesh bakes + final merged bake
                eta_multiplier = mesh_count * format_count if mesh_count > 1 else 1
                
                self._tasks.append(
                    {
                        "material_name": mat_name,
                        "material": material,
                        "meshes": meshes,  # List of meshes for this material
                        "dtp_format": dtp_format,
                        "width": width,
                        "height": height,
                        "render_width": render_width,
                        "render_height": render_height,
                        "img_type": img_type,
                        "optimize": optimize,
                        "display_task": display_task,
                        "megapixels": megapixels,
                        "bake_type": bake_type,
                        "eta_multiplier": eta_multiplier,
                    }
                )

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
        self._awaiting_enter = False

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
                base_eta = self._eta.estimate_task_time(
                    task["bake_type"], task["megapixels"]
                )
                # Apply multiplier for multi-mesh materials
                task_eta = base_eta * task["eta_multiplier"]
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
        # Handle mouse wheel scrolling (works in all states)
        if event.type in ("WHEELUPMOUSE", "WHEELDOWNMOUSE") and self._overlay:
            # WHEELDOWNMOUSE should scroll down (show content below) -> increase offset
            # WHEELUPMOUSE should scroll up (show content above) -> decrease offset
            delta = 1 if event.type == "WHEELDOWNMOUSE" else -1
            self._overlay.handle_scroll(delta)
            return {"RUNNING_MODAL"}

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

            # Block all other input while awaiting confirmation (except wheel, handled above)
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
            mat_name = task["material_name"]
            material = task["material"]
            meshes = task["meshes"]
            megapixels = task["megapixels"]
            bake_type = task["bake_type"]
            dtp_format = task["dtp_format"]

            # Phase 1: Update overlay to show we're about to bake, then return
            # This gives the viewport time to redraw before the blocking bake
            if not self._pending_bake:
                # Handle wait_for_enter flag
                if self._wait_for_enter and not self._awaiting_enter:
                    # Start waiting for Enter key
                    self._awaiting_enter = True
                    self._overlay._current_message = f"Press ENTER to bake {mat_name} / {dtp_format}..."
                    return {"RUNNING_MODAL"}
                
                # Check if we're waiting for Enter
                if self._awaiting_enter:
                    if event.type in ("RET", "NUMPAD_ENTER") and event.value == "PRESS":
                        self._awaiting_enter = False
                        self._pending_bake = True
                    else:
                        # Still waiting
                        return {"RUNNING_MODAL"}

                # Track material changes for ETA
                if mat_name != self._current_material:
                    if self._current_material:
                        self._materials_completed += 1
                    self._current_material = mat_name

                # Update overlay - mark task as active
                self._overlay.set_active_task(self._task_index)

                if not self._wait_for_enter or not self._awaiting_enter:
                    self._pending_bake = True
                return {"RUNNING_MODAL"}

            # Phase 2: Actually perform the bake
            self._pending_bake = False

            # Start timing
            import time

            self._task_start_time = time.perf_counter()
            self._eta.start_task(bake_type, megapixels)

            # Perform the bake using new execute_bake_for_material function
            resolutions = {}
            try:
                resolutions = execute_bake_for_material(
                    self._bake_ctx,
                    mat_name,
                    meshes,
                    debug_print=print,
                )
            except Exception as e:
                print(f"[RunBake] ERROR baking {mat_name} / {dtp_format}: {e}")
                import traceback

                traceback.print_exc()
                resolutions = {}
                self._overlay.set_error(f"Bake failed: {str(e)[:50]}")
                self._awaiting_confirmation = True
                if self._timer:
                    context.window_manager.event_timer_remove(self._timer)
                    self._timer = None
                return {"RUNNING_MODAL"}

            # End timing
            elapsed = time.perf_counter() - self._task_start_time
            self._eta.end_task()

            # Process result - get resolution for this specific format
            if resolutions and dtp_format in resolutions:
                self._baked_count += 1
                width, height = resolutions[dtp_format]
                result_res = f"{width}x{height}"
                self._overlay.mark_task_done(
                    self._task_index, result_res=result_res, elapsed_seconds=elapsed
                )
            else:
                self._failed_count += 1
                self._overlay.mark_task_done(
                    self._task_index, result_res="FAILED", elapsed_seconds=elapsed
                )

            # Recalculate ETAs for remaining pending tasks (scalars may have updated)
            for remaining_task in self._tasks[self._task_index + 1 :]:
                base_eta = self._eta.estimate_task_time(
                    remaining_task["bake_type"], remaining_task["megapixels"]
                )
                # Apply multiplier for multi-mesh materials
                new_eta = base_eta * remaining_task["eta_multiplier"]
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
    NYAATOOLS_OT_StartBakeQueue,
]
