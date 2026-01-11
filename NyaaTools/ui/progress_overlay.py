"""
Progress Overlay for heavy operations.

Draws a fullscreen overlay in the 3D viewport showing:
- Task rows (self-describing, no column headers)
- Status per task (pending, in-progress, done)
- Elapsed time
"""

import bpy
import blf
import math
import time

from .task_system import (
    Task,
    TaskQueue,
    TaskStatus,
    DrawHelper,
    draw_helper,
    default_render_row,
    FONT_SIZE_TITLE,
    FONT_SIZE_BODY,
    FONT_SIZE_SMALL,
    LINE_HEIGHT,
)


# Layout
PADDING = 40
PANEL_VERTICAL_MARGIN = 20


class OverlayState:
    """State machine for the overlay."""

    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class ProgressOverlay:
    """
    Manages the fullscreen progress overlay display.

    Works with Task objects that have inline execute/render_row callables.
    Simple design: just a list of self-describing task rows with elapsed time.

    Usage:
        overlay = ProgressOverlay()
        queue = TaskQueue()
        overlay.start(context, "Operation Title", queue)

        # During operation (tasks can be added dynamically):
        queue.add(task)
        overlay.set_active_task(task_index)
        overlay.mark_task_done(task_index, result_dict, elapsed)

        # When done:
        overlay.set_completed()
        # Wait for user confirmation, then:
        overlay.finish()
    """

    def __init__(self):
        self._handle = None
        self._context = None
        self._title = ""
        self._queue: TaskQueue = None
        self._current_message = ""
        self._is_active = False
        self._state = OverlayState.RUNNING
        self._error_message = ""
        self._saved_ui_state = {}
        self._scroll_offset = 0
        self._draw = draw_helper
        self._manager = None  # Reference to ProgressManager for error handling

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def state(self) -> str:
        return self._state

    @property
    def needs_confirmation(self) -> bool:
        """True if overlay is waiting for user to confirm completion."""
        return self._state in (
            OverlayState.COMPLETED,
            OverlayState.CANCELLED,
            OverlayState.ERROR,
        )

    def start(self, context, title: str, queue: TaskQueue):
        """
        Start the overlay.

        Args:
            context: Blender context
            title: Title to display
            queue: TaskQueue containing tasks to display
        """
        self._context = context
        self._title = title
        self._queue = queue
        self._is_active = True
        self._state = OverlayState.RUNNING
        self._error_message = ""
        self._current_message = "Starting..."

        # Hide UI elements
        self._hide_ui(context)

        # Register draw handler
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_callback, (context,), "WINDOW", "POST_PIXEL"
        )

        # Force redraw
        self._tag_redraw()

    def finish(self):
        """Stop the overlay and clean up."""
        if self._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None

        self._is_active = False

        # Restore UI elements
        self._restore_ui()

        # Force redraw to clear overlay
        self._tag_redraw()

    def _hide_ui(self, context):
        """Hide UI elements for fullscreen overlay."""
        self._saved_ui_state = {}

        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        self._saved_ui_state["show_region_header"] = (
                            space.show_region_header
                        )
                        space.show_region_header = False

                        self._saved_ui_state["show_overlays"] = (
                            space.overlay.show_overlays
                        )
                        space.overlay.show_overlays = False

                        self._saved_ui_state["show_gizmo"] = space.show_gizmo
                        space.show_gizmo = False

                        self._saved_ui_state["show_region_ui"] = space.show_region_ui
                        space.show_region_ui = False

                        self._saved_ui_state["show_region_toolbar"] = (
                            space.show_region_toolbar
                        )
                        space.show_region_toolbar = False

    def _restore_ui(self):
        """Restore hidden UI elements."""
        if not self._context or not self._saved_ui_state:
            return

        try:
            for area in self._context.screen.areas:
                if area.type == "VIEW_3D":
                    for space in area.spaces:
                        if space.type == "VIEW_3D":
                            if "show_region_header" in self._saved_ui_state:
                                space.show_region_header = self._saved_ui_state[
                                    "show_region_header"
                                ]
                            if "show_overlays" in self._saved_ui_state:
                                space.overlay.show_overlays = self._saved_ui_state[
                                    "show_overlays"
                                ]
                            if "show_gizmo" in self._saved_ui_state:
                                space.show_gizmo = self._saved_ui_state["show_gizmo"]
                            if "show_region_ui" in self._saved_ui_state:
                                space.show_region_ui = self._saved_ui_state[
                                    "show_region_ui"
                                ]
                            if "show_region_toolbar" in self._saved_ui_state:
                                space.show_region_toolbar = self._saved_ui_state[
                                    "show_region_toolbar"
                                ]
        except:
            pass  # Context may be invalid

    def set_active_task(self, task_index: int):
        """Mark a task as currently active."""
        task = self._queue.get_task(task_index)
        if task:
            task.status = TaskStatus.ACTIVE
            
            # Check if task has layer name for simplified footer message
            params = task.params
            layer_name = params.get("layer_name", "")
            
            if layer_name:
                self._current_message = f'Merging "{layer_name}"'
            else:
                self._current_message = f"Processing: {task.label}"
            
            self._tag_redraw()

    def mark_task_done(
        self,
        task_index: int,
        result: dict = None,
        elapsed_seconds: float = 0.0,
    ):
        """Mark a task as completed."""
        task = self._queue.get_task(task_index)
        if task:
            task.result = result or {}
            task.elapsed_seconds = elapsed_seconds

            # Determine success from result
            if result and result.get("success", True):
                task.status = TaskStatus.DONE
            else:
                task.status = TaskStatus.FAILED

            self._queue.current_index = task_index + 1
            self._tag_redraw()

    def set_message(self, message: str):
        """Set the current status message."""
        self._current_message = message
        self._tag_redraw()

    def set_completed(self, message: str = ""):
        """Mark the operation as completed, waiting for confirmation."""
        self._state = OverlayState.COMPLETED
        self._current_message = message or "Operation completed!"
        self._scroll_offset = 0
        self._tag_redraw()

    def set_cancelled(self, message: str = ""):
        """Mark the operation as cancelled, waiting for confirmation."""
        self._state = OverlayState.CANCELLED
        self._current_message = message or "Operation cancelled."
        self._scroll_offset = 0

        if self._queue:
            self._queue.mark_remaining_cancelled()

        self._tag_redraw()

    def set_error(self, message: str):
        """Mark the operation as failed, waiting for confirmation."""
        self._state = OverlayState.ERROR
        self._error_message = message
        # Footer shows the error message (without "Error:" prefix - that's in the status)
        self._current_message = message  # Footer message (full error)
        self._scroll_offset = 0
        self._tag_redraw()

    def _get_scroll_constraints(self, context=None):
        """Calculate scroll constraints (available_height, max_scroll)."""
        # Use provided context or fall back to stored context
        ctx = context or self._context
        if not ctx:
            return None, None

        # Try to get region from context, or find it from screen areas
        region = None
        if hasattr(ctx, 'region') and ctx.region:
            region = ctx.region
        elif hasattr(ctx, 'screen') and ctx.screen:
            # Find VIEW_3D area and get its region
            for area in ctx.screen.areas:
                if area.type == "VIEW_3D":
                    # Get the main region (WINDOW type)
                    for reg in area.regions:
                        if reg.type == "WINDOW":
                            region = reg
                            break
                    if region:
                        break

        if not region:
            return None, None

        viewport_height = region.height
        header_height = 60
        footer_height = 80
        available_height = (
            viewport_height
            - 2 * PANEL_VERTICAL_MARGIN
            - header_height
            - footer_height
            - PADDING * 2
        )

        content_height = self._calculate_content_height()
        max_scroll = max(0, content_height - available_height)

        # Clamp scroll_offset if queue shrunk (e.g., tasks removed)
        if self._scroll_offset > max_scroll:
            self._scroll_offset = max_scroll

        return available_height, max_scroll

    def _scroll_to_last_if_needed(self, context=None):
        """Auto-scroll to show the last task if it would be off-screen."""
        if not self._queue or len(self._queue) == 0:
            return

        _, max_scroll = self._get_scroll_constraints(context)
        if max_scroll is None:
            return

        # Check if the last task is off-screen
        # The last task is visible if scroll_offset >= max_scroll
        # If current scroll is less than max, the last task is off-screen
        if self._scroll_offset < max_scroll:
            self._scroll_offset = max_scroll
            self._tag_redraw()

    def handle_scroll(self, delta: int):
        """Handle mouse wheel scroll."""
        available_height, max_scroll = self._get_scroll_constraints(None)
        if available_height is None or max_scroll is None:
            return

        scroll_speed = LINE_HEIGHT * 3
        self._scroll_offset += delta * scroll_speed
        self._scroll_offset = max(0, min(self._scroll_offset, max_scroll))
        self._tag_redraw()

    def _tag_redraw(self):
        """Request viewport redraw."""
        if self._context:
            try:
                # Tag redraw for all VIEW_3D areas and their WINDOW regions
                # This ensures the draw handler gets called in all states
                for area in self._context.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
                        # Also tag the WINDOW region (where our draw handler is registered)
                        for region in area.regions:
                            if region.type == "WINDOW":
                                region.tag_redraw()

                # During RUNNING: use redraw_timer for aggressive updates during heavy operations
                # During confirmation: standard tag_redraw() is enough and avoids cursor flickering
                if self._state == OverlayState.RUNNING:
                    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
            except Exception:
                pass

    def _draw_callback(self, context):
        """GPU draw callback for the overlay."""
        if not self._is_active or not self._queue:
            return

        region = context.region
        if not region:
            return

        # Check if we need to auto-scroll (fallback if called from draw callback)
        # Only check if we have tasks and scroll_offset is 0 (haven't scrolled yet)
        if len(self._queue) > 0 and self._scroll_offset == 0:
            self._scroll_to_last_if_needed(context)

        width = region.width
        height = region.height

        # Draw fullscreen dark background
        self._draw.draw_rect(0, 0, width, height, self._draw.COLOR_BG_DARK)

        # Calculate panel dimensions
        panel_width = int(width * 0.95)
        panel_height = self._calculate_panel_height()
        panel_height = min(panel_height, height - 2 * PANEL_VERTICAL_MARGIN)

        x = (width - panel_width) // 2
        y = height - panel_height - PANEL_VERTICAL_MARGIN

        # Draw panel background
        self._draw.draw_rect(x, y, panel_width, panel_height, self._draw.COLOR_BG_PANEL)

        # Draw header
        header_height = 60
        self._draw.draw_rect(
            x,
            y + panel_height - header_height,
            panel_width,
            header_height,
            self._draw.COLOR_BG_HEADER,
        )

        # Draw title
        self._draw.draw_text(
            self._title,
            x + PADDING,
            y + panel_height - 42,
            FONT_SIZE_TITLE,
            self._draw.COLOR_TEXT,
        )

        # Draw state indicator (HUD Legends)
        hint_x = x + panel_width - PADDING
        hint_y = y + panel_height - 38
        
        # Calculate pulsing yellow for keys
        pulse = (math.sin(time.time() * 6) + 1) / 2
        b = 0.6 + 0.4 * pulse
        pulsing_yellow = (1.0 * b, 0.85 * b, 0.1 * b, 1.0)
        white = (1.0, 1.0, 1.0, 1.0)

        def draw_legend(key: str, action: str, cur_x: int) -> int:
            # Draw from right to left
            # 1. Action text
            act_w = int(blf.dimensions(0, action)[0])
            cur_x -= act_w
            self._draw.draw_text(action, cur_x, hint_y, FONT_SIZE_SMALL, white)
            
            # 2. Spacer
            cur_x -= 4
            
            # 3. Key tag
            key_tag = f"<{key}>"
            key_w = int(blf.dimensions(0, key_tag)[0])
            cur_x -= key_w
            self._draw.draw_text(key_tag, cur_x, hint_y, FONT_SIZE_SMALL, pulsing_yellow)
            
            # 4. Padding for next legend
            return cur_x - 24

        # Set font for width calculations
        blf.size(0, FONT_SIZE_SMALL)
        
        cur_x = hint_x
        if self._state == OverlayState.RUNNING:
            draw_legend("Esc", "Cancel", cur_x)
        elif self._state in (OverlayState.COMPLETED, OverlayState.CANCELLED, OverlayState.ERROR):
            # Check if we should show Debug Inspection
            if self._state in (OverlayState.CANCELLED, OverlayState.ERROR):
                cur_x = draw_legend("PauseBreak", "Debug Inspection", cur_x)
            
            # Everyone gets the Exit button
            draw_legend("Enter", "Exit", cur_x)

        # Content area
        content_top = y + panel_height - header_height - PADDING
        content_bottom = y + PADDING + 80  # Leave room for footer

        current_y = content_top

        # Calculate lines to skip for scrolling
        lines_to_skip = int(self._scroll_offset / LINE_HEIGHT)
        lines_processed = 0

        # Render all tasks as flat list
        for task in self._queue.tasks:
            lines_processed += 1
            if lines_processed <= lines_to_skip:
                continue
            if current_y < content_bottom:
                break

            current_y -= LINE_HEIGHT

            # Use custom render_row if provided, otherwise use default
            # Wrap in try/except to catch render exceptions
            try:
                if task.render_row:
                    task.render_row(task, x + PADDING, current_y, self._draw)
                else:
                    default_render_row(task, x + PADDING, current_y, self._draw)
            except Exception as e:
                # Render exception - defer to next tick (can't call manager methods during GPU draw)
                import traceback
                print(f"[ProgressOverlay] Render error for task '{task.id}': {e}")
                traceback.print_exc()
                task.status = TaskStatus.FAILED
                # Store error to handle on next tick (same as task execution exceptions)
                if self._manager:
                    self._manager._report_error(RuntimeError(str(e)[:100]))
                
                # Draw task row with "Failed" status (status column will show "Failed")
                # Don't draw error message in task row - that goes in footer
                status_color = self._draw.get_status_color(TaskStatus.FAILED)
                status_text = self._draw.get_status_text(TaskStatus.FAILED)
                self._draw.draw_text(status_text, x + PADDING, current_y, FONT_SIZE_BODY, status_color)

        # Draw footer
        self._draw_footer(x, y, panel_width)

    def _draw_footer(self, panel_x: int, panel_y: int, panel_width: int):
        """Draw the footer with status message and elapsed time."""
        footer_y = panel_y + PADDING

        # Current message
        self._draw.draw_text(
            self._current_message,
            panel_x + PADDING,
            footer_y + 35,
            FONT_SIZE_BODY,
            self._draw.COLOR_TEXT,
        )

        # Total elapsed time
        total_elapsed = self._queue.get_total_elapsed() if self._queue else 0
        if total_elapsed > 0:
            elapsed_text = f"Elapsed: {self._draw.format_seconds(total_elapsed)}"
            self._draw.draw_text(
                elapsed_text,
                panel_x + PADDING,
                footer_y + 5,
                FONT_SIZE_BODY,
                self._draw.COLOR_TEXT_DIM,
            )

    def _calculate_content_height(self) -> int:
        """Calculate the height of the scrollable content area."""
        if not self._queue:
            return 0
        return len(self._queue) * LINE_HEIGHT

    def _calculate_panel_height(self) -> int:
        """Calculate the total height needed for the panel."""
        height = 60  # Header
        height += PADDING * 2
        height += 80  # Footer
        height += self._calculate_content_height()
        return max(height, 300)
