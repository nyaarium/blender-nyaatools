"""
Generic Task System for progress overlays.

Provides a reusable task queue and rendering system that any operator can use.
Tasks have inline execute and render_row callables.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import blf
import gpu
from gpu_extras.batch import batch_for_shader


# Font settings
FONT_ID = 0
FONT_SIZE_TITLE = 32
FONT_SIZE_BODY = 18
FONT_SIZE_SMALL = 14

# Layout constants
LINE_HEIGHT = 26


# =============================================================================
# Task Status
# =============================================================================


class TaskStatus(Enum):
    """Status of a task in the queue."""

    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


# =============================================================================
# Draw Helper
# =============================================================================


class DrawHelper:
    """
    Utility class for GPU drawing operations.

    Provides consistent styling and simplifies drawing code.
    """

    def __init__(self):
        self._font_id = FONT_ID

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        size: int = FONT_SIZE_BODY,
        color: Optional[Tuple[float, float, float, float]] = None,
    ) -> int:
        """
        Draw text at the specified position.

        Returns:
            Width of the drawn text in pixels.
        """
        if color is None:
            color = self.COLOR_TEXT
        blf.size(self._font_id, size)
        blf.color(self._font_id, *color)
        blf.position(self._font_id, x, y, 0)
        blf.draw(self._font_id, text)
        # Get text width for layout
        return int(blf.dimensions(self._font_id, text)[0])

    def draw_rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: Tuple[float, float, float, float],
    ) -> None:
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

    def format_seconds(self, seconds: float) -> str:
        """Format seconds as human-readable string."""
        if seconds <= 0:
            return "—"
        if seconds < 60:
            return f"{int(seconds)}s"
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"

    def get_status_color(self, status: TaskStatus) -> Tuple[float, float, float, float]:
        """Get the color for a task status."""
        if status == TaskStatus.DONE:
            return self.COLOR_STATUS_DONE
        elif status == TaskStatus.ACTIVE:
            return self.COLOR_STATUS_ACTIVE
        elif status == TaskStatus.FAILED:
            return self.COLOR_STATUS_FAILED
        elif status == TaskStatus.CANCELLED:
            return self.COLOR_STATUS_ACTIVE
        else:
            return self.COLOR_STATUS_PENDING

    def get_status_text(self, status: TaskStatus) -> str:
        """Get display text for a task status."""
        if status == TaskStatus.DONE:
            return "Done"
        elif status == TaskStatus.ACTIVE:
            return "Running"
        elif status == TaskStatus.FAILED:
            return "Failed"
        elif status == TaskStatus.CANCELLED:
            return "Cancelled"
        else:
            return "Pending"

    # Color properties
    @property
    def COLOR_BG_DARK(self) -> Tuple[float, float, float, float]:
        return (0.05, 0.05, 0.08, 0.95)

    @property
    def COLOR_BG_PANEL(self) -> Tuple[float, float, float, float]:
        return (0.12, 0.12, 0.15, 1.0)

    @property
    def COLOR_BG_HEADER(self) -> Tuple[float, float, float, float]:
        return (0.18, 0.18, 0.25, 1.0)

    @property
    def COLOR_TEXT(self) -> Tuple[float, float, float, float]:
        return (0.95, 0.95, 0.95, 1.0)

    @property
    def COLOR_TEXT_DIM(self) -> Tuple[float, float, float, float]:
        return (0.55, 0.55, 0.6, 1.0)

    @property
    def COLOR_TEXT_HIGHLIGHT(self) -> Tuple[float, float, float, float]:
        return (0.4, 0.85, 1.0, 1.0)

    @property
    def COLOR_STATUS_DONE(self) -> Tuple[float, float, float, float]:
        return (0.35, 0.85, 0.4, 1.0)

    @property
    def COLOR_STATUS_ACTIVE(self) -> Tuple[float, float, float, float]:
        return (1.0, 0.75, 0.25, 1.0)

    @property
    def COLOR_STATUS_FAILED(self) -> Tuple[float, float, float, float]:
        return (1.0, 0.35, 0.35, 1.0)

    @property
    def COLOR_STATUS_PENDING(self) -> Tuple[float, float, float, float]:
        return (0.55, 0.55, 0.6, 1.0)

    @property
    def COLOR_TYPE(self) -> Tuple[float, float, float, float]:
        return (0.7, 0.5, 0.9, 1.0)

    @property
    def FONT_SIZE_BODY(self) -> int:
        return FONT_SIZE_BODY

    @property
    def FONT_SIZE_SMALL(self) -> int:
        return FONT_SIZE_SMALL


# Singleton instance for convenience
draw_helper = DrawHelper()


# =============================================================================
# Task
# =============================================================================


@dataclass
class Task:
    """
    A single task in the queue.

    Each task has:
    - An ID for tracking
    - A label for display
    - An execute callable that performs the work
    - Optional render_row callable for custom display
    - Status tracking
    - Params dict for extra data
    - Result dict for output data (filled after execution)
    - Elapsed time after completion
    """

    id: str
    label: str
    execute: Callable[[Any], Dict[str, Any]]
    status: TaskStatus = TaskStatus.PENDING
    params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    elapsed_seconds: float = 0.0
    render_row: Optional[Callable[["Task", int, int, DrawHelper], int]] = None


# Column widths for consistent alignment
COL_WIDTH_STATUS = 100  # Status column (Pending, Active, Done, Failed)
COL_WIDTH_TIME = 80  # Time column (1m 23s format)


def default_render_row(task: Task, x: int, y: int, draw: DrawHelper) -> int:
    """
    Default task row rendering: [Status] [Time] [Label]

    Args:
        task: The task to render
        x: Left edge X position
        y: Baseline Y position
        draw: DrawHelper for drawing operations

    Returns:
        Height consumed (LINE_HEIGHT)
    """
    col_x = x

    # Status column (fixed width)
    status_color = draw.get_status_color(task.status)
    status_text = draw.get_status_text(task.status)
    draw.draw_text(status_text, col_x, y, FONT_SIZE_BODY, status_color)
    col_x += COL_WIDTH_STATUS

    # Time column (fixed width, always show)
    time_text = draw.format_seconds(task.elapsed_seconds)
    draw.draw_text(time_text, col_x, y, FONT_SIZE_BODY, status_color)
    col_x += COL_WIDTH_TIME

    # Label (flexible width)
    draw.draw_text(task.label, col_x, y, FONT_SIZE_BODY, draw.COLOR_TEXT)

    return LINE_HEIGHT


# =============================================================================
# TaskQueue
# =============================================================================


class TaskQueue:
    """
    Manages an ordered list of tasks.

    Supports dynamic task addition during operation.
    """

    def __init__(self):
        self._tasks: List[Task] = []
        self._current_index: int = 0

    def add(self, task: Task) -> None:
        """Add a task to the queue."""
        self._tasks.append(task)

    def add_all(self, tasks: List[Task]) -> None:
        """Add multiple tasks to the queue."""
        self._tasks.extend(tasks)

    def clear(self) -> None:
        """Clear all tasks from the queue."""
        self._tasks.clear()
        self._current_index = 0

    @property
    def tasks(self) -> List[Task]:
        """Get all tasks in order."""
        return self._tasks

    @property
    def current_index(self) -> int:
        """Get the current task index (number of completed tasks)."""
        return self._current_index

    @current_index.setter
    def current_index(self, value: int) -> None:
        """Set the current task index."""
        self._current_index = value

    def __len__(self) -> int:
        return len(self._tasks)

    def __getitem__(self, index: int) -> Task:
        return self._tasks[index]

    def get_task(self, index: int) -> Optional[Task]:
        """Get task by index, or None if out of bounds."""
        if 0 <= index < len(self._tasks):
            return self._tasks[index]
        return None

    def count_by_status(self, status: TaskStatus) -> int:
        """Count tasks with the given status."""
        return sum(1 for t in self._tasks if t.status == status)

    def mark_remaining_cancelled(self) -> None:
        """Mark all pending tasks as cancelled."""
        for task in self._tasks:
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED

    def get_total_elapsed(self) -> float:
        """Get total elapsed time across all completed tasks."""
        return sum(t.elapsed_seconds for t in self._tasks if t.elapsed_seconds > 0)
