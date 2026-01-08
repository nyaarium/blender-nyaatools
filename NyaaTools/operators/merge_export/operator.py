"""
Asset Merge & Export Operator.

Merges mesh layers and exports assets in various formats (FBX, OBJ, VotV)
or to a __Export__ collection. Uses the ProgressManager to handle modal boilerplate.
"""

import traceback

import bpy
from bpy.props import BoolProperty, StringProperty

from ...asset.asset_lookup import get_asset_by_name

from .generator import (
    MergeExportConfig,
    MergeExportState,
    create_merge_export_generator,
    setup_merge_export,
    cleanup_merge_export,
)


class NYAATOOLS_OT_AssetMergeExport(bpy.types.Operator):
    """Merge layers and export asset with progress overlay."""

    bl_idname = "nyaa.asset_merge_export"
    bl_label = "Merge & Export"
    bl_options = {"REGISTER"}

    asset_name: StringProperty(name="Asset Name", default="")
    export_format: StringProperty(name="Export Format", default="fbx")
    target_type: StringProperty(name="Target Type", default="file")
    export_static: BoolProperty(name="Export Static", default=False)
    bake_after_export: BoolProperty(name="Bake After Export", default=False)
    include_ue_colliders: BoolProperty(name="Include UE Colliders", default=False)

    # State
    _config: MergeExportConfig = None
    _state: MergeExportState = None

    def invoke(self, context, event):
        try:
            # Validation
            if not self.asset_name:
                self.report({"ERROR"}, "Specify an asset name.")
                return {"CANCELLED"}

            asset_host = get_asset_by_name(self.asset_name)
            if not asset_host:
                self.report({"ERROR"}, f"Asset '{self.asset_name}' not found.")
                return {"CANCELLED"}

            if self.bake_after_export:
                cfg = asset_host.nyaa_asset
                if len(cfg.bake_images) == 0:
                    self.report(
                        {"ERROR"},
                        '"Bake after export" requires bake profiles to be configured.',
                    )
                    return {"CANCELLED"}

            # Create config and state
            self._config = MergeExportConfig(
                asset_host=asset_host,
                asset_name=self.asset_name,
                export_format=self.export_format,
                target_type=self.target_type,
                export_static=self.export_static,
                bake_after_export=self.bake_after_export,
                include_ue_colliders=self.include_ue_colliders,
            )
            self._state = MergeExportState()

            # Run setup
            if not setup_merge_export(self._config, self._state, self._debug_print):
                self.report({"ERROR"}, "Setup failed")
                return {"CANCELLED"}

            # Determine title based on target
            title = "Merge & Export"
            if self.target_type == "collection":
                title = "Export to Collection"

            # Run via ProgressManager (late import to get current class after hot reload)
            from ...ui.ProgressManager import ProgressManager

            manager = ProgressManager.get()
            return manager.execute(
                context,
                title=title,
                generator=create_merge_export_generator(
                    self._config, self._state, self._debug_print
                ),
                on_cleanup=lambda reason: self._cleanup(reason),
                sync=False,
            )

        except Exception as error:
            print(traceback.format_exc())
            if self._state:
                cleanup_merge_export(
                    self._config, self._state, "error", self._debug_print
                )
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

    def _cleanup(self, reason: str):
        """Cleanup callback."""
        msg = cleanup_merge_export(self._config, self._state, reason, self._debug_print)

        if reason == "success":
            self.report({"INFO"}, msg)
        elif reason == "cancel":
            self.report({"WARNING"}, msg)
        # Don't report on error - the error handler already did

        self._config = None
        self._state = None

    def _debug_print(self, *msgs):
        print("   ", *msgs)
