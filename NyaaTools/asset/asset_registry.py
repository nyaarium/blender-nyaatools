"""
Asset Registry - Manages asset identity and duplicate detection.

This module provides:
- Unique ID assignment for assets
- Duplicate detection when objects are copied (Shift+D)
- Automatic renaming of duplicated assets to prevent name collisions
- Mesh pointer retargeting for duplicated hierarchies

The registry uses Blender's depsgraph_update_post handler to detect when
objects are duplicated. When a duplicate is detected (same UUID as an
existing asset), it:
1. Assigns a new unique UUID
2. Retargets mesh references to the duplicate's children
3. Renames the asset to avoid name collision
"""

import bpy
import re
import uuid
from bpy.app.handlers import persistent


class AssetRegistry:
    """
    Singleton registry for tracking asset IDs and detecting duplicates.

    The registry maintains a mapping of UUID -> Object for all registered assets.
    When the depsgraph updates, it checks for ID collisions which indicate
    a duplicate operation occurred.
    """

    def __init__(self):
        self._id_map: dict[str, bpy.types.Object] = {}

    def clear(self):
        """Clear all registered assets. Called on file load."""
        self._id_map.clear()

    def get_owner(self, asset_id: str) -> bpy.types.Object | None:
        """Get the object that owns a given asset ID, or None if not registered."""
        return self._id_map.get(asset_id)

    def register(self, obj: bpy.types.Object) -> str:
        """
        Register an asset and return its ID.
        Generates a new UUID if the asset doesn't have one.
        """
        if not obj.nyaa_asset.id:
            obj.nyaa_asset.id = str(uuid.uuid4())

        self._id_map[obj.nyaa_asset.id] = obj
        return obj.nyaa_asset.id

    def claim(self, asset_id: str, obj: bpy.types.Object):
        """Claim an existing ID for an object."""
        self._id_map[asset_id] = obj

    def prune_invalid(self):
        """Remove entries for objects that no longer exist."""
        to_remove = []
        for aid, obj in list(self._id_map.items()):
            try:
                if not obj or obj.name not in bpy.data.objects:
                    to_remove.append(aid)
            except ReferenceError:
                to_remove.append(aid)

        for aid in to_remove:
            del self._id_map[aid]


# Module-level singleton
_registry = AssetRegistry()


def get_registry() -> AssetRegistry:
    """Get the global asset registry instance."""
    return _registry


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def _strip_numeric_suffix(name: str) -> str:
    """Remove Blender's .001, .002 etc suffix from a name."""
    if "." in name and name.rsplit(".", 1)[1].isdigit():
        return name.rsplit(".", 1)[0]
    return name


def _retarget_mesh_references(obj: bpy.types.Object):
    """
    Retarget mesh pointers for a duplicated asset.

    When an asset hierarchy is duplicated, the mesh references in the config
    still point to the original meshes. This function finds the corresponding
    duplicated meshes (children of the new asset) and updates the references.
    """
    cfg = obj.nyaa_asset

    for entry in cfg.meshes:
        target = entry.mesh_object
        if not target:
            continue

        # Already pointing to our own child - no retargeting needed
        if target.parent == obj:
            continue

        # Find a child that matches the original mesh's base name
        for child in obj.children:
            if _strip_numeric_suffix(child.name) == _strip_numeric_suffix(target.name):
                entry.mesh_object = child
                break


def _has_name_collision(obj: bpy.types.Object) -> bool:
    """
    Check if the asset's name collides with another asset.

    Returns True if there's a collision, False otherwise.
    """
    cfg = obj.nyaa_asset
    current_name = cfg.asset_name
    if not current_name:
        return False

    # Check if any other asset has the same name
    for o in bpy.data.objects:
        if o != obj and hasattr(o, "nyaa_asset") and o.nyaa_asset.is_asset:
            if o.nyaa_asset.asset_name == current_name:
                return True
    return False


def _ensure_unique_asset_name(obj: bpy.types.Object):
    """
    Ensure asset name is unique by appending a number if needed.

    Format: "{Name} {N}" where N starts at 2.
    Example: "Hero" -> "Hero 2" -> "Hero 3"
    """
    cfg = obj.nyaa_asset
    current_name = cfg.asset_name
    if not current_name:
        return

    # Parse existing number suffix if present
    match = re.match(r"^(.*) (\d+)$", current_name)
    if match:
        base_name = match.group(1)
        start_count = int(match.group(2)) + 1
    else:
        base_name = current_name
        start_count = 2

    # Collect all used asset names (excluding self)
    used_names = set()
    for o in bpy.data.objects:
        if o != obj and hasattr(o, "nyaa_asset") and o.nyaa_asset.is_asset:
            used_names.add(o.nyaa_asset.asset_name)

    # Name is already unique
    if current_name not in used_names:
        return

    # Find next available number
    count = start_count
    while True:
        candidate = f"{base_name} {count}"
        if candidate not in used_names:
            cfg.asset_name = candidate
            break
        count += 1


# -----------------------------------------------------------------------------
# Blender Handlers
# -----------------------------------------------------------------------------


@persistent
def _on_depsgraph_update(scene, depsgraph):
    """
    Handler for depsgraph updates - detects asset duplication.

    When an asset is duplicated (Shift+D), the new object initially has the
    same UUID as the original. This handler detects that collision and:
    1. Assigns a new UUID to the duplicate
    2. Retargets mesh references
    3. Ensures the asset name is unique
    """
    if not depsgraph.updates:
        return

    registry = get_registry()
    registry.prune_invalid()

    # Track IDs processed in this handler invocation to avoid reprocessing
    processed_ids: set[str] = set()

    for update in depsgraph.updates:
        obj = update.id

        if not isinstance(obj, bpy.types.Object):
            continue

        # CRITICAL: Get the original object, not the evaluated copy.
        # Writing properties to evaluated objects does NOT persist!
        if hasattr(obj, "is_evaluated") and obj.is_evaluated:
            obj = obj.original

        if not hasattr(obj, "nyaa_asset") or not obj.nyaa_asset.is_asset:
            continue

        # Ensure all assets have an ID
        if not obj.nyaa_asset.id:
            registry.register(obj)

        current_id = obj.nyaa_asset.id

        # Skip if already processed in this invocation
        if current_id in processed_ids:
            continue

        # Check for ID collision (indicates duplication)
        existing_owner = registry.get_owner(current_id)

        if existing_owner and existing_owner != obj:
            # COLLISION: This object is a duplicate of existing_owner
            new_id = str(uuid.uuid4())
            obj.nyaa_asset.id = new_id
            registry.claim(new_id, obj)
            processed_ids.add(new_id)

            # Fix up the duplicate
            _retarget_mesh_references(obj)
            # Only rename if there's a name collision
            if _has_name_collision(obj):
                _ensure_unique_asset_name(obj)

        elif not existing_owner:
            # Unknown ID (e.g., loaded from file) - claim it
            registry.claim(current_id, obj)
            processed_ids.add(current_id)


@persistent
def _on_load_post(dummy):
    """
    Handler for file load - rebuilds the asset registry.

    Scans all objects and registers any that are marked as assets.
    Objects without .NNN suffixes are processed first to ensure they
    claim their IDs before any duplicates.
    """
    registry = get_registry()
    registry.clear()

    # Sort: objects without numeric suffix first (they're likely the "originals")
    def sort_key(o):
        has_suffix = "." in o.name and o.name.rsplit(".", 1)[1].isdigit()
        return (1 if has_suffix else 0, o.name)

    for obj in sorted(bpy.data.objects, key=sort_key):
        if hasattr(obj, "nyaa_asset") and obj.nyaa_asset.is_asset:
            registry.register(obj)


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


def register():
    """
    Register Blender handlers for asset duplicate detection.

    Must be called AFTER PropertyGroups are attached to bpy.types.Object,
    as the handlers access obj.nyaa_asset.
    """
    bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update)
    bpy.app.handlers.load_post.append(_on_load_post)


def unregister():
    """Unregister handlers and clear the registry."""
    if _on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph_update)
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)

    # Clean up state
    _registry.clear()
