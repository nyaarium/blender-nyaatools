"""
Migration and legacy operators for NyaaTools panel.
"""

import bpy
from bpy.types import Operator
from bpy.props import StringProperty

from ..legacy import (
    PROP_AVATAR_EXPORT_PATH,
    PROP_AVATAR_LAYERS,
    PROP_AVATAR_NAME,
)
from .panels_context import (
    scene_has_legacy_data,
    scene_has_old_avatar_data,
    invalidate_selection_cache,
)
from ..armature.estimate_humanoid_ratio import is_humanoid


def _sort_asset_meshes(meshes_collection):
    """
    Sort meshes collection: non-colliders first (by layer, then name),
    then colliders last (by name).
    """
    # Build list of (index, entry) tuples
    entries = [(i, entry) for i, entry in enumerate(meshes_collection)]

    # Sort with colliders last
    def sort_key(item):
        _, entry = item
        if entry.is_ue_collider:
            # Colliders: sort last, by mesh name
            return (1, "", entry.mesh_object.name if entry.mesh_object else "")
        else:
            # Non-colliders: sort by layer name, then mesh name
            return (
                0,
                entry.layer_name,
                entry.mesh_object.name if entry.mesh_object else "",
            )

    entries.sort(key=sort_key)

    # Reorder collection using .move()
    for new_index, (old_index, _) in enumerate(entries):
        if old_index != new_index:
            # Find current position (may have changed due to previous moves)
            current_index = old_index
            for prev_new, (prev_old, _) in enumerate(entries[:new_index]):
                if prev_old < old_index:
                    current_index -= 1
            meshes_collection.move(current_index, new_index)


# =============================================================================
# Migration Operators
# =============================================================================


class NYAATOOLS_OT_MigrateLegacyData(Operator):
    """Migrate legacy NyaaTools custom properties to V2 format"""

    bl_idname = "nyaatools.migrate_legacy_data"
    bl_label = "Upgrade Legacy Data"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return scene_has_legacy_data(context)

    def execute(self, context):
        migrated_avatars = 0
        migrated_meshes = 0

        avatar_armatures = {}

        for obj in bpy.data.objects:
            if obj.type != "ARMATURE":
                continue
            if PROP_AVATAR_NAME not in obj:
                continue

            avatar_name = obj[PROP_AVATAR_NAME]
            if not avatar_name:
                continue

            obj.nyaa_asset.is_asset = True
            obj.nyaa_asset.asset_name = avatar_name
            obj.nyaa_asset.is_humanoid = is_humanoid(obj)

            if PROP_AVATAR_EXPORT_PATH in obj:
                export_path = obj[PROP_AVATAR_EXPORT_PATH]
                if export_path:
                    profile = obj.nyaa_asset.export_profiles.add()
                    # Normalize path separators and ensure it ends with separator
                    normalized_path = export_path.replace("\\", "/").rstrip("/") + "/"
                    profile.path = normalized_path

                    # Auto-detect VotV export paths
                    if normalized_path.endswith("/Assets/meshes/printer/"):
                        profile.format = "votv"
                        profile.include_ue_colliders = True
                    else:
                        profile.format = "fbx"

            avatar_armatures[avatar_name] = obj
            migrated_avatars += 1

            if PROP_AVATAR_NAME in obj:
                del obj[PROP_AVATAR_NAME]
            if PROP_AVATAR_EXPORT_PATH in obj:
                del obj[PROP_AVATAR_EXPORT_PATH]

        # Add all UCX_ meshes in scene as colliders to each asset
        # (old system only supported 1 asset at a time, so all UCX was included)
        for avatar_name, armature in avatar_armatures.items():
            for scene_obj in bpy.data.objects:
                if scene_obj.type != "MESH":
                    continue
                if not scene_obj.name.upper().startswith("UCX_"):
                    continue

                # Check if already added
                already_exists = any(
                    entry.mesh_object == scene_obj
                    for entry in armature.nyaa_asset.meshes
                )
                if already_exists:
                    continue

                entry = armature.nyaa_asset.meshes.add()
                entry.mesh_object = scene_obj
                entry.layer_name = "UCX"
                entry.is_ue_collider = True
                migrated_meshes += 1

        for obj in bpy.data.objects:
            if obj.type != "MESH":
                continue
            if PROP_AVATAR_LAYERS not in obj:
                continue

            layers_str = obj[PROP_AVATAR_LAYERS]
            if not layers_str:
                del obj[PROP_AVATAR_LAYERS]
                continue

            for layer_entry in layers_str.split(","):
                layer_entry = layer_entry.strip()
                if "/" not in layer_entry:
                    continue

                parts = layer_entry.split("/", 1)
                avatar_name = parts[0].strip()
                layer_name = parts[1].strip() if len(parts) > 1 else "Base"

                armature = avatar_armatures.get(avatar_name)
                if armature is None:
                    continue

                already_exists = any(
                    entry.mesh_object == obj for entry in armature.nyaa_asset.meshes
                )
                if already_exists:
                    continue

                entry = armature.nyaa_asset.meshes.add()
                entry.mesh_object = obj

                # Auto-detect UCX_ meshes as colliders
                if obj.name.upper().startswith("UCX_"):
                    entry.layer_name = "UCX"
                    entry.is_ue_collider = True
                else:
                    entry.layer_name = layer_name
                migrated_meshes += 1

            del obj[PROP_AVATAR_LAYERS]

        # Sort all migrated assets
        for armature in avatar_armatures.values():
            _sort_asset_meshes(armature.nyaa_asset.meshes)

        invalidate_selection_cache()
        self.report(
            {"INFO"},
            f"Migrated {migrated_avatars} asset(s) and {migrated_meshes} mesh assignment(s)",
        )
        return {"FINISHED"}


class NYAATOOLS_OT_MigrateAvatarToAsset(Operator):
    """Migrate from nyaa_avatar PropertyGroup to nyaa_asset"""

    bl_idname = "nyaatools.migrate_avatar_to_asset"
    bl_label = "Upgrade Avatar to Asset"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return scene_has_old_avatar_data(context)

    def execute(self, context):
        migrated = 0
        migrated_assets = []

        for obj in bpy.data.objects:
            if not hasattr(obj, "nyaa_avatar"):
                continue
            if not obj.nyaa_avatar.is_avatar:
                continue

            old = obj.nyaa_avatar
            new = obj.nyaa_asset

            new.is_asset = True
            new.asset_name = old.avatar_name
            # Pre-compute humanoid flag for armatures
            if obj.type == "ARMATURE":
                new.is_humanoid = is_humanoid(obj)

            for old_entry in old.meshes:
                new_entry = new.meshes.add()
                new_entry.mesh_object = old_entry.mesh_object

                # Auto-detect UCX_ meshes as colliders
                if (
                    old_entry.mesh_object
                    and old_entry.mesh_object.name.upper().startswith("UCX_")
                ):
                    new_entry.layer_name = "UCX"
                    new_entry.is_ue_collider = True
                else:
                    new_entry.layer_name = old_entry.layer_name

            for old_profile in old.export_profiles:
                new_profile = new.export_profiles.add()

                # Normalize path separators and ensure it ends with separator
                normalized_path = old_profile.path.replace("\\", "/").rstrip("/") + "/"
                new_profile.path = normalized_path

                # Auto-detect VotV export paths
                if normalized_path.endswith("/Assets/meshes/printer/"):
                    new_profile.format = "votv"
                    new_profile.include_ue_colliders = True
                else:
                    new_profile.format = old_profile.format

            for old_bake in old.bake_images:
                new_bake = new.bake_images.add()
                new_bake.format = old_bake.format
                new_bake.image_type = old_bake.image_type
                new_bake.width = old_bake.width
                new_bake.height = old_bake.height

            old.is_avatar = False
            old.avatar_name = ""
            old.meshes.clear()
            old.export_profiles.clear()
            old.bake_images.clear()

            migrated += 1
            migrated_assets.append(obj)

        # Add all UCX_ meshes in scene as colliders to each migrated asset
        # (old system only supported 1 asset at a time, so all UCX was included)
        migrated_colliders = 0
        for asset_obj in migrated_assets:
            for scene_obj in bpy.data.objects:
                if scene_obj.type != "MESH":
                    continue
                if not scene_obj.name.upper().startswith("UCX_"):
                    continue

                # Check if already added
                already_exists = any(
                    entry.mesh_object == scene_obj
                    for entry in asset_obj.nyaa_asset.meshes
                )
                if already_exists:
                    continue

                entry = asset_obj.nyaa_asset.meshes.add()
                entry.mesh_object = scene_obj
                entry.layer_name = "UCX"
                entry.is_ue_collider = True
                migrated_colliders += 1

        # Sort all migrated assets
        for asset_obj in migrated_assets:
            _sort_asset_meshes(asset_obj.nyaa_asset.meshes)

        invalidate_selection_cache()

        if migrated_colliders > 0:
            self.report(
                {"INFO"},
                f"Migrated {migrated} avatar(s) to unified asset system and added {migrated_colliders} UCX collider(s)",
            )
        else:
            self.report(
                {"INFO"}, f"Migrated {migrated} avatar(s) to unified asset system"
            )
        return {"FINISHED"}


MIGRATE_OPERATOR_CLASSES = [
    NYAATOOLS_OT_MigrateLegacyData,
    NYAATOOLS_OT_MigrateAvatarToAsset,
]
