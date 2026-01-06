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
    invalidate_selection_cache,
)
from ..armature.estimate_humanoid_ratio import is_humanoid


def _sort_asset_meshes(meshes_collection):
    """
    Sort meshes collection: non-colliders first (by layer, then name),
    then colliders last (by name).
    """

    def sort_key(entry):
        if entry.is_ue_collider:
            return (1, "", entry.mesh_object.name.lower() if entry.mesh_object else "")
        else:
            return (
                0,
                entry.layer_name.lower(),
                entry.mesh_object.name.lower() if entry.mesh_object else "",
            )

    # Selection sort using .move() - simple and correct
    n = len(meshes_collection)
    for target_pos in range(n):
        # Find the minimum element among positions target_pos to n-1
        min_idx = target_pos
        min_key = sort_key(meshes_collection[target_pos])
        for j in range(target_pos + 1, n):
            j_key = sort_key(meshes_collection[j])
            if j_key < min_key:
                min_idx = j
                min_key = j_key
        # Move the minimum to target_pos
        if min_idx != target_pos:
            meshes_collection.move(min_idx, target_pos)


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


MIGRATE_OPERATOR_CLASSES = [
    NYAATOOLS_OT_MigrateLegacyData,
]
