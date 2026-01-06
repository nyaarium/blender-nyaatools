"""
Selection context and legacy data detection for NyaaTools panel.
"""

import time

import bpy

from ..legacy import (
    PROP_AVATAR_EXPORT_PATH,
    PROP_AVATAR_LAYERS,
    PROP_AVATAR_NAME,
)
from ..asset.asset_helpers import find_asset_for_mesh


# =============================================================================
# Legacy Data Detection
# =============================================================================


def has_legacy_avatar_data(obj) -> bool:
    """Check if an object has legacy NyaaTools custom properties."""
    if obj is None:
        return False
    if PROP_AVATAR_NAME in obj:
        return True
    if PROP_AVATAR_EXPORT_PATH in obj:
        return True
    if PROP_AVATAR_LAYERS in obj:
        return True
    return False


def selection_has_legacy_data(context) -> bool:
    """Check if any selected object has legacy data. Uses cached SelectionContext."""
    return get_selection_context(context).has_legacy_data


def scene_has_legacy_data(context) -> bool:
    """Check if any object in scene has legacy data."""
    for obj in bpy.data.objects:
        if has_legacy_avatar_data(obj):
            return True
    return False


# =============================================================================
# Selection Context Cache
# =============================================================================

# Module-level cache for SelectionContext
_cached_selection_context = None
_cached_selection_key = None
_cache_timestamp = 0.0

# Cache TTL in seconds - short enough to catch selection changes between redraws,
# long enough to share across all panels in a single draw cycle
_CACHE_TTL = 0.016  # ~1 frame at 60fps


def get_selection_context(context):
    """
    Get a cached SelectionContext, rebuilding only if selection changed.

    Uses time-based caching to share the same context across all panels
    within a single draw cycle, while still detecting selection changes.
    """
    global _cached_selection_context, _cached_selection_key, _cache_timestamp

    now = time.monotonic()

    # Fast path: if cache is fresh (same draw cycle), skip key computation
    if _cached_selection_context is not None and (now - _cache_timestamp) < _CACHE_TTL:
        return _cached_selection_context

    # Build selection key: (count, tuple of object ids)
    selected = context.selected_objects
    current_key = (len(selected), tuple(id(obj) for obj in selected))

    # If key matches and cache exists, just refresh timestamp
    if _cached_selection_key == current_key and _cached_selection_context is not None:
        _cache_timestamp = now
        return _cached_selection_context

    # Rebuild cache
    _cached_selection_context = SelectionContext(context)
    _cached_selection_key = current_key
    _cache_timestamp = now
    return _cached_selection_context


def invalidate_selection_cache():
    """Call this when asset data changes to force a rebuild."""
    global _cached_selection_context, _cached_selection_key, _cache_timestamp
    _cached_selection_context = None
    _cached_selection_key = None
    _cache_timestamp = 0.0


def tag_view3d_redraw(context):
    """
    Request an immediate redraw for VIEW_3D UI panels.
    Ensures panel UIs reflect data changes without waiting for another event.
    """
    # Prefer the current area if available (cheaper than scanning all windows)
    area = getattr(context, "area", None)
    if area and area.type == "VIEW_3D":
        area.tag_redraw()
        for region in area.regions:
            if region.type == "UI":
                region.tag_redraw()
        return

    wm = getattr(context, "window_manager", None)
    if wm is None:
        return

    for window in wm.windows:
        screen = getattr(window, "screen", None)
        if not screen:
            continue
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            area.tag_redraw()
            for region in area.regions:
                if region.type == "UI":
                    region.tag_redraw()


# =============================================================================
# Selection Context
# =============================================================================


class SelectionContext:
    """
    Analyzes current selection once per draw cycle.
    Avoids repeated iteration over selected objects.

    Use get_selection_context(context) to get a cached instance.
    """

    __slots__ = (
        "armatures",
        "meshes",
        "armature",
        "asset",
        "is_humanoid",
        "meshes_belonging_to",
        "has_legacy_data",
    )

    def __init__(self, context):
        self.armatures = []
        self.meshes = []
        self.armature = None
        self.asset = None
        self.is_humanoid = False
        self.meshes_belonging_to = []
        self.has_legacy_data = False

        for obj in context.selected_objects:
            if obj.type == "ARMATURE":
                self.armatures.append(obj)
            elif obj.type == "MESH":
                self.meshes.append(obj)
            # Check legacy data while iterating (avoids second pass)
            if not self.has_legacy_data and has_legacy_avatar_data(obj):
                self.has_legacy_data = True

        if len(self.armatures) == 1:
            self.armature = self.armatures[0]

        self._find_asset()

    def _find_asset(self):
        """Determine the current asset context."""
        # Check for armature asset first (priority when exactly one armature)
        if self.armature and hasattr(self.armature, "nyaa_asset"):
            if self.armature.nyaa_asset.is_asset:
                self.asset = self.armature
                # Use cached humanoid flag (set during asset creation)
                self.is_humanoid = self.armature.nyaa_asset.is_humanoid
                return

        # Check for mesh assets in selection (even with multiple meshes selected)
        # This allows selecting a mesh asset + other meshes to add
        mesh_assets = []
        for mesh in self.meshes:
            if hasattr(mesh, "nyaa_asset") and mesh.nyaa_asset.is_asset:
                mesh_assets.append(mesh)

        if len(mesh_assets) == 1 and len(self.armatures) == 0:
            # Exactly one mesh asset selected (possibly with non-asset meshes)
            self.asset = mesh_assets[0]
            self.is_humanoid = False
            return

        # If multiple mesh assets selected, don't pick one - let panel show jumplist
        # (meshes_belonging_to will be populated below)

        # Track which assets non-asset meshes belong to
        for mesh in self.meshes:
            if mesh in mesh_assets:
                continue  # Skip mesh assets themselves
            belonging = find_asset_for_mesh(mesh)
            self.meshes_belonging_to.extend(belonging)

    @property
    def has_asset(self) -> bool:
        return self.asset is not None

    @property
    def is_asset(self) -> bool:
        return self.asset is not None

    @property
    def exactly_one_armature(self):
        return len(self.armatures) == 1

    @property
    def exactly_two_armatures(self):
        return len(self.armatures) == 2 and len(self.meshes) == 0

    @property
    def has_armature(self):
        return len(self.armatures) >= 1

    @property
    def has_meshes(self):
        return len(self.meshes) >= 1

    @property
    def has_meshes_for_asset(self):
        return self.has_asset and self.meshes
