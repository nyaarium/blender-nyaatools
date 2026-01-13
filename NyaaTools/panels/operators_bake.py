"""
Bake UI operators and helpers for NyaaTools panel.

This module contains only the UI-related bake operators (add/edit/remove bake images,
load profile). The actual bake queue operator is in operators/bake/.
"""

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty

from .panels_context import SelectionContext, tag_view3d_redraw


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
# Bake Image Dialog Helpers
# =============================================================================


def get_bake_format_from_operator(operator) -> str:
    """Get the DTP format string from a bake image operator's properties."""
    if operator.template == "custom":
        channels = [operator.r_channel, operator.g_channel, operator.b_channel]
        if operator.a_channel != "xx":
            channels.append(operator.a_channel)
        return "-".join(channels)
    return operator.template


def draw_bake_image_ui(layout, operator, context):
    """Shared draw logic for bake image Add/Edit dialogs."""
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
# Bake UI Operators
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

        tag_view3d_redraw(context)

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

        tag_view3d_redraw(context)

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

        tag_view3d_redraw(context)

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

        tag_view3d_redraw(context)

        self.report({"INFO"}, f"Removed bake image: {name}")
        return {"FINISHED"}


# =============================================================================
# Helper Functions (kept for compatibility)
# =============================================================================


def _ensure_object_accessible(obj):
    """Ensure an object is accessible for selection and baking."""
    if not obj:
        return

    obj.hide_viewport = False
    obj.hide_render = False
    obj.hide_set(False)

    view_layer = bpy.context.view_layer
    for collection in obj.users_collection:
        collection.hide_viewport = False
        collection.hide_render = False

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


