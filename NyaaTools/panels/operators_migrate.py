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
    SelectionContext,
    scene_has_legacy_data,
    scene_has_old_avatar_data,
    invalidate_selection_cache,
)
from ..armature.estimate_humanoid_ratio import is_humanoid


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
                    profile.path = export_path
                    profile.format = "fbx"

            avatar_armatures[avatar_name] = obj
            migrated_avatars += 1

            if PROP_AVATAR_NAME in obj:
                del obj[PROP_AVATAR_NAME]
            if PROP_AVATAR_EXPORT_PATH in obj:
                del obj[PROP_AVATAR_EXPORT_PATH]

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
                entry.layer_name = layer_name
                migrated_meshes += 1

            del obj[PROP_AVATAR_LAYERS]

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
                new_entry.layer_name = old_entry.layer_name

            for old_profile in old.export_profiles:
                new_profile = new.export_profiles.add()
                new_profile.path = old_profile.path
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

        invalidate_selection_cache()
        self.report({"INFO"}, f"Migrated {migrated} avatar(s) to unified asset system")
        return {"FINISHED"}


# =============================================================================
# Legacy Operators (backward compatibility)
# =============================================================================


class NYAATOOLS_OT_MarkAsAvatar(Operator):
    """Mark the selected armature as an avatar (legacy - redirects to asset)"""

    bl_idname = "nyaatools.mark_as_avatar"
    bl_label = "Mark as Avatar"
    bl_options = {"REGISTER", "UNDO"}

    avatar_name: StringProperty(name="Avatar Name", default="")

    @classmethod
    def poll(cls, context):
        return (
            len(context.selected_objects) == 1
            and context.selected_objects[0].type == "ARMATURE"
        )

    def invoke(self, context, event):
        arm = context.selected_objects[0]
        if not self.avatar_name:
            self.avatar_name = arm.name
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        self.layout.prop(self, "avatar_name")

    def execute(self, context):
        arm = context.selected_objects[0]
        arm.nyaa_asset.is_asset = True
        arm.nyaa_asset.asset_name = self.avatar_name
        self.report({"INFO"}, f"Marked '{arm.name}' as asset '{self.avatar_name}'")
        return {"FINISHED"}


class NYAATOOLS_OT_UnmarkAvatar(Operator):
    """Remove avatar status from the selected armature (legacy)"""

    bl_idname = "nyaatools.unmark_avatar"
    bl_label = "Unmark Avatar"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if len(context.selected_objects) != 1:
            return False
        obj = context.selected_objects[0]
        return (
            obj.type == "ARMATURE"
            and hasattr(obj, "nyaa_asset")
            and obj.nyaa_asset.is_asset
        )

    def execute(self, context):
        arm = context.selected_objects[0]
        name = arm.nyaa_asset.asset_name
        arm.nyaa_asset.is_asset = False
        arm.nyaa_asset.asset_name = ""
        arm.nyaa_asset.meshes.clear()
        self.report({"INFO"}, f"Removed asset status from '{name}'")
        return {"FINISHED"}


class NYAATOOLS_OT_BakeMaterialSlots(Operator):
    """Bake all material slots with configurable options"""

    bl_idname = "nyaatools.bake_material_slots"
    bl_label = "Bake Material Slots"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.active_object
            and context.active_object.type == "MESH"
            and len(context.selected_objects) == 1
        )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        settings = context.scene.nyaa_settings.bake

        layout.label(text="Bake Settings", icon="IMAGE_DATA")

        row = layout.row()
        row.label(text="Resolution:")
        row.prop(settings, "resolution", text="")

        layout.separator()
        layout.label(text="Textures to Bake:")

        col = layout.column(align=True)
        col.prop(settings, "include_rgba")
        col.prop(settings, "include_orm")
        col.prop(settings, "include_normal")
        col.prop(settings, "include_emission")

    def execute(self, context):
        return bpy.ops.nyaa.bake_material_slots()


class NYAATOOLS_OT_AvatarExport(Operator):
    """Merge and export avatar with current settings (legacy)"""

    bl_idname = "nyaatools.avatar_export"
    bl_label = "Merge & Export"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        if not sel.has_asset:
            return False
        if sel.asset.type == "ARMATURE":
            return len(sel.asset.nyaa_asset.meshes) > 0
        return True

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        settings = context.scene.nyaa_settings.export

        return bpy.ops.nyaa.avatar_merge_export(
            avatar_name=cfg.asset_name,
            export_format=settings.format,
        )


MIGRATE_OPERATOR_CLASSES = [
    NYAATOOLS_OT_MigrateLegacyData,
    NYAATOOLS_OT_MigrateAvatarToAsset,
    NYAATOOLS_OT_MarkAsAvatar,
    NYAATOOLS_OT_UnmarkAvatar,
    NYAATOOLS_OT_BakeMaterialSlots,
    NYAATOOLS_OT_AvatarExport,
]
