"""
Bake Operator.

Bakes textures from materials with progress overlay.
Uses the ProgressManager to handle modal boilerplate.
"""

import bpy
from bpy.types import Operator

from ...bake.bake_context import (
    get_pending_bake_context,
    has_pending_bake_context,
    BakeContext,
)

from .generator import create_bake_generator, BakeState


class NYAATOOLS_OT_StartBakeQueue(Operator):
    """Start baking textures with progress overlay"""

    bl_idname = "nyaatools.start_bake_queue"
    bl_label = "Start Bake Queue"
    bl_options = {"REGISTER"}

    # State
    _bake_ctx: BakeContext = None
    _state: BakeState = None

    @classmethod
    def poll(cls, context):
        return has_pending_bake_context()

    def invoke(self, context, event):
        # Get pending bake context
        ctx = get_pending_bake_context()
        if not ctx:
            self.report({"ERROR"}, "No pending bake context")
            return {"CANCELLED"}

        self._bake_ctx = ctx
        self._state = BakeState()

        print(f"[RunBake] Starting bake with {len(ctx.mesh_metas)} mesh metas")

        # Ensure object mode
        if context.active_object and context.active_object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        # Run via ProgressManager (late import to get current class after hot reload)
        from ...ui.ProgressManager import ProgressManager

        manager = ProgressManager.get()
        return manager.execute(
            context,
            title="Baking Textures",
            generator=create_bake_generator(self._bake_ctx, self._state, print),
            on_cleanup=lambda reason: self._cleanup(reason),
            sync=False,
        )

    def _cleanup(self, reason: str):
        """Cleanup callback."""
        ctx = self._bake_ctx
        state = self._state

        result_msg = f"Baked {state.baked_count} textures"
        if state.failed_count > 0:
            result_msg += f", {state.failed_count} failed"
        if ctx and ctx.export_dir:
            result_msg += f". Output: {ctx.export_dir}"

        # Call context cleanup (may be set by merge-export for baked material assignment)
        if ctx and ctx.on_cleanup:
            try:
                ctx.on_cleanup(reason)
                print("[RunBake] Cleanup callback executed")
            except Exception as e:
                print(f"[RunBake] Cleanup callback error: {e}")

        if reason == "success":
            if state.failed_count > 0:
                self.report({"WARNING"}, result_msg)
            else:
                self.report({"INFO"}, result_msg)
        elif reason == "cancel":
            self.report({"WARNING"}, f"Cancelled. {result_msg}")

        self._bake_ctx = None
        self._state = None
