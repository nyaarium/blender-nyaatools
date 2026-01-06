"""
Progress Overlay for heavy operations.

Draws a fullscreen overlay in the 3D viewport showing:
- Material sections with bake tasks
- Status per task (pending, in-progress, done)
- Progress bar and ETA
"""

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader


# Colors (RGBA)
COLOR_BG_DARK = (0.05, 0.05, 0.08, 0.95)
COLOR_BG_PANEL = (0.12, 0.12, 0.15, 1.0)
COLOR_BG_HEADER = (0.18, 0.18, 0.25, 1.0)
COLOR_TEXT = (0.95, 0.95, 0.95, 1.0)
COLOR_TEXT_DIM = (0.55, 0.55, 0.6, 1.0)
COLOR_TEXT_HIGHLIGHT = (0.4, 0.85, 1.0, 1.0)
COLOR_PROGRESS_BG = (0.2, 0.2, 0.25, 1.0)
COLOR_PROGRESS_FG = (0.25, 0.7, 0.35, 1.0)
COLOR_STATUS_DONE = (0.35, 0.85, 0.4, 1.0)
COLOR_STATUS_ACTIVE = (1.0, 0.75, 0.25, 1.0)
COLOR_STATUS_FAILED = (1.0, 0.35, 0.35, 1.0)
COLOR_BUTTON = (0.25, 0.5, 0.8, 1.0)
COLOR_BUTTON_HOVER = (0.35, 0.6, 0.9, 1.0)

# Font settings
FONT_ID = 0
FONT_SIZE_TITLE = 32
FONT_SIZE_HEADER = 22
FONT_SIZE_BODY = 18
FONT_SIZE_SMALL = 14

# Layout
PADDING = 40
LINE_HEIGHT = 26
COLUMN_HEADER_PADDING = 8
COLUMN_WIDTHS = [120, 100, 180, 70, 480]  # status, time, dtp, type, resolution
PANEL_VERTICAL_MARGIN = 20


class BakeTask:
    """Represents a single bake task for display."""

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    def __init__(
        self,
        material_name: str,
        dtp_format: str,
        image_type: str,
        resolution: str,
        optimize: bool,
    ):
        self.material_name = material_name
        self.dtp_format = dtp_format
        self.image_type = image_type.upper()
        self.resolution = (
            resolution  # e.g., "2048x2048" or "2048" if square (max resolution)
        )
        self.render_resolution = ""  # e.g., "64x64" (detected render resolution)
        self.optimize = optimize
        self.status = self.STATUS_PENDING
        self.result_resolution = ""  # e.g., "256x256" after optimization
        self.elapsed_seconds = 0.0  # Actual time taken (for done tasks)
        self.estimated_seconds = 0.0  # ETA (for pending tasks)


class OverlayState:
    """State machine for the overlay."""

    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class ProgressOverlay:
    """
    Manages the fullscreen progress overlay display.

    Usage:
        overlay = ProgressOverlay()
        overlay.start(context, "Baking Textures", tasks_by_material)

        # During operation:
        overlay.set_active_task(task_index, phase="R,G,B")
        overlay.mark_task_done(task_index, result_res="2048x2048")
        overlay.update_progress(current, total, eta_str)

        # When done:
        overlay.set_completed()  # or set_error(message)
        # Wait for user confirmation, then:
        overlay.finish()
    """

    def __init__(self):
        self._handle = None
        self._context = None
        self._title = ""
        self._tasks_by_material = {}  # {material_name: [BakeTask, ...]}
        self._material_order = []  # Ordered list of material names
        self._task_list = []  # Flat list for indexing
        self._current = 0
        self._total = 0
        self._eta_str = ""
        self._current_message = ""
        self._is_active = False
        self._state = OverlayState.RUNNING
        self._error_message = ""
        self._saved_ui_state = {}
        self._scroll_offset = 0  # Vertical scroll offset in pixels

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

    def start(self, context, title: str, tasks_by_material: dict):
        """
        Start the overlay.

        Args:
            context: Blender context
            title: Title to display
            tasks_by_material: Dict of {material_name: [BakeTask, ...]}
        """
        self._context = context
        self._title = title
        self._tasks_by_material = tasks_by_material
        self._material_order = list(tasks_by_material.keys())
        self._is_active = True
        self._state = OverlayState.RUNNING
        self._error_message = ""

        # Build flat task list
        self._task_list = []
        for mat_name in self._material_order:
            self._task_list.extend(tasks_by_material[mat_name])

        self._total = len(self._task_list)
        self._current = 0
        self._eta_str = ""
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
                        # Save and hide header (top toolbar)
                        self._saved_ui_state["show_region_header"] = (
                            space.show_region_header
                        )
                        space.show_region_header = False

                        # Save and hide overlays
                        self._saved_ui_state["show_overlays"] = (
                            space.overlay.show_overlays
                        )
                        space.overlay.show_overlays = False

                        # Save and hide gizmos
                        self._saved_ui_state["show_gizmo"] = space.show_gizmo
                        space.show_gizmo = False

                        # Save and hide N-panel (region_ui)
                        self._saved_ui_state["show_region_ui"] = space.show_region_ui
                        space.show_region_ui = False

                        # Save and hide T-panel (region_toolbar)
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
                            # Restore header (top toolbar)
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

    def set_active_task(self, task_index: int, phase: str = ""):
        """Mark a task as currently active."""
        if 0 <= task_index < len(self._task_list):
            task = self._task_list[task_index]
            task.status = BakeTask.STATUS_ACTIVE
            task.active_phase = phase
            self._current_message = (
                f"Baking: {task.dtp_format} for {task.material_name}"
            )
            if phase:
                self._current_message += f" [{phase}]"
            self._tag_redraw()

    def mark_task_done(
        self, task_index: int, result_res: str = "", elapsed_seconds: float = 0.0
    ):
        """Mark a task as completed."""
        if 0 <= task_index < len(self._task_list):
            task = self._task_list[task_index]
            if result_res == "FAILED":
                task.status = BakeTask.STATUS_FAILED
                task.result_resolution = ""
            else:
                task.status = BakeTask.STATUS_DONE
                task.result_resolution = result_res
            task.elapsed_seconds = elapsed_seconds
            self._current = task_index + 1
            self._tag_redraw()

    def update_progress(self, current: int, total: int, eta_str: str = ""):
        """Update the progress bar and ETA."""
        self._current = current
        self._total = total
        self._eta_str = eta_str
        self._tag_redraw()

    def set_completed(self, message: str = ""):
        """Mark the operation as completed, waiting for confirmation."""
        self._state = OverlayState.COMPLETED
        self._current_message = message or "Bake completed!"
        self._scroll_offset = 0  # Reset scroll when completed
        self._tag_redraw()

    def set_cancelled(self, message: str = ""):
        """Mark the operation as cancelled, waiting for confirmation."""
        self._state = OverlayState.CANCELLED
        self._current_message = message or "Bake cancelled."
        self._scroll_offset = 0  # Reset scroll when cancelled

        # Mark all future tasks (from current index onwards) as cancelled
        for task_idx in range(self._current, len(self._task_list)):
            task = self._task_list[task_idx]
            # Only mark pending tasks as cancelled (don't override done/failed/active)
            if task.status == BakeTask.STATUS_PENDING:
                task.status = BakeTask.STATUS_CANCELLED

        self._tag_redraw()

    def set_error(self, message: str):
        """Mark the operation as failed, waiting for confirmation."""
        self._state = OverlayState.ERROR
        self._error_message = message
        self._current_message = f"Error: {message}"
        self._scroll_offset = 0  # Reset scroll when error
        self._tag_redraw()

    def handle_scroll(self, delta: int):
        """Handle mouse wheel scroll.

        Args:
            delta: Positive for scroll down (WHEELDOWNMOUSE), negative for scroll up (WHEELUPMOUSE)
        """
        if not self._context or not self._context.region:
            return

        # Calculate max scroll based on content height
        content_height = self._calculate_content_height()
        viewport_height = self._context.region.height
        header_height = 60
        footer_height = 120
        available_height = (
            viewport_height
            - 2 * PANEL_VERTICAL_MARGIN
            - header_height
            - footer_height
            - PADDING * 2
            - COLUMN_HEADER_PADDING
            - 25
        )

        max_scroll = max(0, content_height - available_height)

        # Update scroll offset
        # Positive delta (scroll down/WHEELDOWNMOUSE) should increase offset to show content below
        # Negative delta (scroll up/WHEELUPMOUSE) should decrease offset to show content above
        scroll_speed = LINE_HEIGHT * 3  # Scroll 3 lines at a time
        self._scroll_offset += delta * scroll_speed
        self._scroll_offset = max(0, min(self._scroll_offset, max_scroll))
        self._tag_redraw()

    def _tag_redraw(self):
        """Request viewport redraw."""
        if self._context:
            try:
                for area in self._context.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
            except:
                pass  # Context may be invalid

    def _draw_callback(self, context):
        """GPU draw callback for the overlay."""
        if not self._is_active:
            return

        # Get viewport dimensions
        region = context.region
        if not region:
            return

        width = region.width
        height = region.height

        # Draw fullscreen dark background
        self._draw_rect(0, 0, width, height, COLOR_BG_DARK)

        # Calculate panel dimensions (full width with margin, full height with tiny margin)
        panel_width = int(width * 0.95)
        panel_height = self._calculate_panel_height()
        panel_height = min(panel_height, height - 2 * PANEL_VERTICAL_MARGIN)

        # Center horizontally, position at top with tiny margin
        x = (width - panel_width) // 2
        y = height - panel_height - PANEL_VERTICAL_MARGIN

        # Draw panel background
        self._draw_rect(x, y, panel_width, panel_height, COLOR_BG_PANEL)

        # Draw header
        header_height = 60
        self._draw_rect(
            x,
            y + panel_height - header_height,
            panel_width,
            header_height,
            COLOR_BG_HEADER,
        )

        # Draw title
        self._draw_text(
            self._title, x + PADDING, y + panel_height - 42, FONT_SIZE_TITLE, COLOR_TEXT
        )

        # Draw state indicator
        if self._state == OverlayState.RUNNING:
            hint_text = "Press ESC to cancel after this bake"
            hint_color = COLOR_TEXT_DIM
        elif self._state == OverlayState.COMPLETED:
            hint_text = "COMPLETED - Press ENTER to close"
            hint_color = COLOR_STATUS_DONE
        elif self._state == OverlayState.CANCELLED:
            hint_text = "CANCELLED - Press ENTER to close"
            hint_color = COLOR_STATUS_ACTIVE
        else:  # ERROR
            hint_text = "ERROR - Press ENTER to close"
            hint_color = COLOR_STATUS_FAILED

        self._draw_text(
            hint_text,
            x + panel_width - PADDING - 350,
            y + panel_height - 38,
            FONT_SIZE_SMALL,
            hint_color,
        )

        # Draw content area
        content_top = y + panel_height - header_height - PADDING
        content_bottom = y + PADDING + 120  # Leave room for footer

        # Column headers - always shown at fixed position (not scrolled)
        header_y = content_top - COLUMN_HEADER_PADDING
        self._draw_column_headers(x + PADDING, header_y, prominent=True)

        # Separator line under column headers
        separator_y = header_y - 10
        self._draw_rect(
            x + PADDING, separator_y, panel_width - 2 * PADDING, 2, COLOR_TEXT_DIM
        )

        # Start drawing from normal position
        current_y = separator_y - 15

        # Calculate how many lines to skip based on scroll offset
        lines_to_skip = int(self._scroll_offset / LINE_HEIGHT)

        # Determine if we should expand all (when not running)
        expand_all = self._state != OverlayState.RUNNING
        current_material_index = (
            self._get_current_material_index() if not expand_all else 0
        )

        # Track how many lines we've processed (for skipping)
        lines_processed = 0

        # Material sections
        for mat_idx, mat_name in enumerate(self._material_order):
            tasks = self._tasks_by_material[mat_name]

            # Determine if this material should be collapsed
            # When not running, expand all. Otherwise collapse based on progress
            should_collapse = not expand_all and mat_idx < current_material_index - 1

            if should_collapse:
                # Collapsed: show only material name and total time
                lines_processed += 1
                if lines_processed <= lines_to_skip:
                    continue  # Skip this line
                if current_y < content_bottom:
                    break  # Would overflow
                current_y -= LINE_HEIGHT
                total_time = sum(
                    task.elapsed_seconds
                    for task in tasks
                    if task.status == BakeTask.STATUS_DONE
                )
                mat_text = f"{mat_name} ({len(tasks)} tasks, {self._format_seconds(total_time)})"
                self._draw_text(
                    mat_text, x + PADDING, current_y, FONT_SIZE_BODY, COLOR_TEXT_DIM
                )
            else:
                # Expanded: show material name and tasks
                lines_processed += 1
                if lines_processed <= lines_to_skip:
                    # Skip material name, but count tasks too
                    for task in tasks:
                        lines_processed += 1
                    continue
                if current_y < content_bottom:
                    break  # Would overflow
                current_y -= LINE_HEIGHT
                self._draw_text(
                    mat_name,
                    x + PADDING,
                    current_y,
                    FONT_SIZE_BODY,
                    COLOR_TEXT_HIGHLIGHT,
                )

                # Tasks directly under material name
                for task in tasks:
                    if current_y < content_bottom:
                        break
                    lines_processed += 1
                    if lines_processed <= lines_to_skip:
                        continue  # Skip this task
                    current_y -= LINE_HEIGHT
                    self._draw_task_row(x + PADDING, current_y, task)

        # Draw footer
        self._draw_footer(x, y, panel_width)

    def _draw_column_headers(self, x: int, y: int, prominent: bool = False):
        """Draw column headers."""
        col_x = x
        headers = ["Status", "Time", "DTP Format", "Type", "Resolution"]

        font_size = FONT_SIZE_HEADER if prominent else FONT_SIZE_SMALL
        color = COLOR_TEXT if prominent else COLOR_TEXT_DIM

        for i, header in enumerate(headers):
            self._draw_text(header, col_x, y, font_size, color)
            col_x += COLUMN_WIDTHS[i]

    def _draw_task_row(self, x: int, y: int, task: BakeTask):
        """Draw a single task row."""
        col_x = x

        # Status column
        if task.status == BakeTask.STATUS_DONE:
            self._draw_text("Done", col_x, y, FONT_SIZE_BODY, COLOR_STATUS_DONE)
        elif task.status == BakeTask.STATUS_FAILED:
            self._draw_text("Failed", col_x, y, FONT_SIZE_BODY, COLOR_STATUS_FAILED)
        elif task.status == BakeTask.STATUS_CANCELLED:
            self._draw_text("Cancelled", col_x, y, FONT_SIZE_BODY, COLOR_STATUS_ACTIVE)
        elif task.status == BakeTask.STATUS_ACTIVE:
            self._draw_text("Baking", col_x, y, FONT_SIZE_BODY, COLOR_STATUS_ACTIVE)
        else:
            self._draw_text("—", col_x, y, FONT_SIZE_BODY, COLOR_TEXT_DIM)
        col_x += COLUMN_WIDTHS[0]

        # Time column (ETA for pending, elapsed for done)
        if task.status == BakeTask.STATUS_DONE:
            time_text = self._format_seconds(task.elapsed_seconds)
            self._draw_text(time_text, col_x, y, FONT_SIZE_BODY, COLOR_STATUS_DONE)
        elif task.status == BakeTask.STATUS_FAILED:
            self._draw_text("—", col_x, y, FONT_SIZE_BODY, COLOR_STATUS_FAILED)
        elif task.status == BakeTask.STATUS_CANCELLED:
            self._draw_text("—", col_x, y, FONT_SIZE_BODY, COLOR_STATUS_ACTIVE)
        elif task.status == BakeTask.STATUS_ACTIVE:
            self._draw_text("...", col_x, y, FONT_SIZE_BODY, COLOR_STATUS_ACTIVE)
        elif task.estimated_seconds > 0:
            time_text = f"~{self._format_seconds(task.estimated_seconds)}"
            self._draw_text(time_text, col_x, y, FONT_SIZE_BODY, COLOR_TEXT_DIM)
        col_x += COLUMN_WIDTHS[1]

        # DTP format
        self._draw_text(task.dtp_format, col_x, y, FONT_SIZE_BODY, COLOR_TEXT)
        col_x += COLUMN_WIDTHS[2]

        # Image type
        self._draw_text(task.image_type, col_x, y, FONT_SIZE_BODY, COLOR_TEXT_DIM)
        col_x += COLUMN_WIDTHS[3]

        # Resolution (shows max -> render -> optimized for <= mode)
        if task.optimize:
            res_prefix = "<="
            res_text = f"{res_prefix}{task.resolution}"
            if task.render_resolution:
                res_text += f" -> {task.render_resolution}"
            if task.status == BakeTask.STATUS_DONE and task.result_resolution:
                res_text += f" -> {task.result_resolution}"
        else:
            res_text = task.resolution
            if task.status == BakeTask.STATUS_DONE and task.result_resolution:
                res_text += f" -> {task.result_resolution}"
        self._draw_text(res_text, col_x, y, FONT_SIZE_BODY, COLOR_TEXT_DIM)

    def _format_seconds(self, seconds: float) -> str:
        """Format seconds as human-readable string."""
        if seconds <= 0:
            return "—"
        if seconds < 60:
            return f"{int(seconds)}s"
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"

    def _draw_footer(self, panel_x: int, panel_y: int, panel_width: int):
        """Draw the footer with progress bar and status."""
        footer_y = panel_y + PADDING

        # Progress bar
        bar_x = panel_x + PADDING
        bar_width = panel_width - 2 * PADDING - 80  # Leave room for percentage
        bar_height = 16
        progress = self._current / max(self._total, 1)

        self._draw_rect(bar_x, footer_y + 70, bar_width, bar_height, COLOR_PROGRESS_BG)
        self._draw_rect(
            bar_x,
            footer_y + 70,
            int(bar_width * progress),
            bar_height,
            COLOR_PROGRESS_FG,
        )

        # Percentage
        percent = int(progress * 100)
        self._draw_text(
            f"{percent}%",
            bar_x + bar_width + 15,
            footer_y + 68,
            FONT_SIZE_HEADER,
            COLOR_TEXT,
        )

        # Current message
        self._draw_text(
            self._current_message,
            panel_x + PADDING,
            footer_y + 35,
            FONT_SIZE_BODY,
            COLOR_TEXT,
        )

        # ETA (only when running)
        if self._eta_str and self._state == OverlayState.RUNNING:
            self._draw_text(
                f"ETA: {self._eta_str}",
                panel_x + PADDING,
                footer_y + 5,
                FONT_SIZE_BODY,
                COLOR_TEXT_DIM,
            )

    def _get_current_material_index(self) -> int:
        """Get the index of the material currently being processed.

        Returns the material index for the task at self._current (which represents
        the number of completed tasks, so the current/active task is at that index).
        """
        if not self._task_list:
            return 0

        # self._current is the count of completed tasks (1-indexed)
        # The current/active task is at index self._current (0-indexed)
        # If all tasks are done, use the last task
        current_task_idx = min(self._current, len(self._task_list) - 1)

        if current_task_idx < 0:
            return 0

        current_task = self._task_list[current_task_idx]

        # Find material index
        for mat_idx, mat_name in enumerate(self._material_order):
            if current_task.material_name == mat_name:
                return mat_idx

        return 0

    def _calculate_content_height(self) -> int:
        """Calculate the height of the scrollable content area."""
        height = COLUMN_HEADER_PADDING + 25  # Column headers and separator

        # When not running, expand all materials
        if self._state != OverlayState.RUNNING:
            # All expanded
            for mat_name in self._material_order:
                tasks = self._tasks_by_material[mat_name]
                height += LINE_HEIGHT  # Material name
                height += len(tasks) * LINE_HEIGHT  # Tasks
        else:
            # Collapse based on current progress
            current_material_index = self._get_current_material_index()
            for mat_idx, mat_name in enumerate(self._material_order):
                tasks = self._tasks_by_material[mat_name]
                should_collapse = mat_idx < current_material_index - 1
                if should_collapse:
                    height += LINE_HEIGHT  # Collapsed: just material name
                else:
                    height += LINE_HEIGHT  # Material name
                    height += len(tasks) * LINE_HEIGHT  # Tasks

        return height

    def _calculate_panel_height(self) -> int:
        """Calculate the total height needed for the panel."""
        height = 60  # Header
        height += PADDING * 2  # Top and bottom padding
        height += 120  # Footer (progress bar, message, eta)

        # Column headers (once at top)
        height += COLUMN_HEADER_PADDING  # Column headers
        height += 25  # Separator and spacing

        # Add content height
        height += self._calculate_content_height()

        return max(height, 300)

    def _draw_rect(self, x: int, y: int, width: int, height: int, color: tuple):
        """Draw a filled rectangle."""
        vertices = [
            (x, y),
            (x + width, y),
            (x + width, y + height),
            (x, y + height),
        ]
        indices = [(0, 1, 2), (0, 2, 3)]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.blend_set("NONE")

    def _draw_text(self, text: str, x: int, y: int, size: int, color: tuple):
        """Draw text at the specified position."""
        blf.size(FONT_ID, size)
        blf.color(FONT_ID, *color)
        blf.position(FONT_ID, x, y, 0)
        blf.draw(FONT_ID, text)
