"""
Progress Manager - Generator-based modal operator system.

Provides a singleton manager that handles all modal boilerplate for
progress-displaying operations. Operators define generator functions
that yield tasks, and the manager handles execution, UI, and cleanup.

Supports nested generators with per-generator cleanups via ChainGenerator.
"""

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Tuple

import bpy

from .task_system import Task, TaskQueue, TaskStatus, DrawHelper
from .progress_overlay import ProgressOverlay


# =============================================================================
# Yield Commands
# =============================================================================


@dataclass
class AddTask:
    """Yield command: Add a task to the queue."""

    task: Task


@dataclass
class ChainGenerator:
    """
    Yield command: Chain another generator with optional cleanup.

    When the chained generator exhausts, its on_cleanup is called before
    resuming the parent generator. This enables nested operations like:

        yield ChainGenerator(bake_generator(), on_cleanup=bake_cleanup)

    The bake_cleanup will be called when bake_generator finishes,
    then the parent generator continues/completes.
    """

    generator: Generator
    on_cleanup: Optional[Callable[[str], None]] = None


# =============================================================================
# Internal Modal Operator
# =============================================================================


class NYAATOOLS_OT_ProgressModalOperator(bpy.types.Operator):
    """Internal modal operator used by ProgressManager."""

    bl_idname = "nyaatools._progress_modal"
    bl_label = "Progress Modal"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        manager = ProgressManager.get()
        if not manager._is_running:
            return {"CANCELLED"}

        wm = context.window_manager
        manager._timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        manager = ProgressManager.get()

        # Handle mouse wheel scrolling
        if event.type in ("WHEELUPMOUSE", "WHEELDOWNMOUSE"):
            if manager._overlay:
                delta = 1 if event.type == "WHEELDOWNMOUSE" else -1
                manager._overlay.handle_scroll(delta)
            return {"RUNNING_MODAL"}

        # Handle confirmation state - wait for ENTER to close
        if manager._awaiting_confirmation:
            if event.type in ("RET", "NUMPAD_ENTER") and event.value == "PRESS":
                manager._finish(context)
                return {"FINISHED"}
            return {"RUNNING_MODAL"}

        # Handle ESC to cancel
        if event.type == "ESC" and event.value == "PRESS":
            manager._handle_cancel(context)
            return {"RUNNING_MODAL"}

        # Timer tick - advance generator
        if event.type == "TIMER":
            result = manager._tick(context)
            return result

        return {"PASS_THROUGH"}


# =============================================================================
# Progress Manager Singleton
# =============================================================================


class ProgressManager:
    """
    Singleton manager for generator-based progress operations.

    Handles all modal boilerplate, allowing operators to focus on
    their core logic expressed as generators.

    Supports nested generators with per-generator cleanups. When a
    ChainGenerator is yielded with on_cleanup, that cleanup is called
    when the chained generator exhausts (before returning to parent).

    Usage:
        manager = ProgressManager.get()
        return manager.execute(
            context,
            title="My Operation",
            generator=my_generator(),
            on_cleanup=my_cleanup_fn,
            sync=False,
        )
    """

    _instance: Optional["ProgressManager"] = None

    @classmethod
    def get(cls) -> "ProgressManager":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._is_running = False
        # Stack of (generator, cleanup) tuples
        self._generator_stack: List[
            Tuple[Generator, Optional[Callable[[str], None]]]
        ] = []
        self._queue: Optional[TaskQueue] = None
        self._overlay: Optional[ProgressOverlay] = None
        self._timer = None
        self._context = None
        self._title = ""
        self._awaiting_confirmation = False
        self._current_task_index = 0
        self._pending_execute = False
        self._task_start_time = 0.0
        self._error_message = ""
        self._completion_reason = "success"
        self._cancelled = False

    @property
    def is_running(self) -> bool:
        """Check if an operation is currently running."""
        return self._is_running

    def execute(
        self,
        context,
        title: str,
        generator: Generator,
        on_cleanup: Optional[Callable[[str], None]] = None,
        sync: bool = False,
    ) -> Set[str]:
        """
        Run a generator-based operation.

        Args:
            context: Blender context
            title: Overlay title
            generator: Generator that yields AddTask/ChainGenerator
            on_cleanup: Called with 'success'|'error'|'cancel' when done
            sync: If True, drain generator synchronously (for nested calls)

        Returns:
            {'FINISHED'} if sync, {'RUNNING_MODAL'} if async
        """
        if sync:
            return self._execute_sync(generator, on_cleanup)

        # Check if already running - chain onto existing operation
        if self._is_running:
            self._generator_stack.append((generator, on_cleanup))
            return {"RUNNING_MODAL"}

        # Start new operation
        self._is_running = True
        self._generator_stack = [(generator, on_cleanup)]
        self._queue = TaskQueue()
        self._overlay = ProgressOverlay()
        self._context = context
        self._title = title
        self._awaiting_confirmation = False
        self._current_task_index = 0
        self._pending_execute = False
        self._error_message = ""
        self._completion_reason = "success"
        self._cancelled = False

        # Ensure object mode
        if context.active_object and context.active_object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        # Start overlay
        self._overlay.start(context, title, self._queue)
        self._overlay.set_message("Starting...")

        # Start internal modal operator
        bpy.ops.nyaatools._progress_modal("INVOKE_DEFAULT")

        return {"RUNNING_MODAL"}

    def _execute_sync(
        self,
        generator: Generator,
        on_cleanup: Optional[Callable[[str], None]] = None,
    ) -> Set[str]:
        """Execute a generator synchronously without UI."""
        queue = TaskQueue()
        # Stack of (generator, cleanup) tuples
        generators: List[Tuple[Generator, Optional[Callable[[str], None]]]] = [
            (generator, on_cleanup)
        ]
        reason = "success"

        try:
            while generators:
                gen, cleanup = generators[-1]
                try:
                    cmd = next(gen)
                    # Use duck-typing to handle class identity issues after hot reload
                    cmd_type = type(cmd).__name__ if cmd else None

                    if cmd_type == "AddTask":
                        task = cmd.task
                        queue.add(task)
                        # Execute immediately
                        try:
                            result = task.execute(None)
                            task.status = TaskStatus.DONE
                            task.result = result
                        except Exception as e:
                            task.status = TaskStatus.FAILED
                            task.result = {"success": False, "error": str(e)}
                            raise
                    elif cmd_type == "ChainGenerator":
                        generators.append((cmd.generator, cmd.on_cleanup))
                except StopIteration:
                    # Generator exhausted - call its cleanup
                    if cleanup:
                        try:
                            cleanup(reason)
                        except Exception as e:
                            print(f"[ProgressManager] Sync cleanup error: {e}")
                    generators.pop()

        except Exception as e:
            print(f"[ProgressManager] Sync execution error: {e}")
            traceback.print_exc()
            reason = "error"
            # Call remaining cleanups on error
            while generators:
                _, cleanup = generators.pop()
                if cleanup:
                    try:
                        cleanup(reason)
                    except Exception as ce:
                        print(f"[ProgressManager] Sync cleanup error: {ce}")

        return {"FINISHED"}

    def _tick(self, context) -> Set[str]:
        """Process one timer tick - advance generator or execute task."""
        # If cancelled, don't advance generators or execute tasks
        if self._cancelled:
            # Let generators finish naturally, but don't process new commands
            if not self._generator_stack:
                return {"RUNNING_MODAL"}
            # Try to advance to let generator finish, but ignore commands
            gen, cleanup = self._generator_stack[-1]
            try:
                cmd = next(gen)
                # Ignore command - we're cancelled
                return {"RUNNING_MODAL"}
            except StopIteration:
                # Generator finished - call cleanup with cancel
                if cleanup:
                    try:
                        cleanup("cancel")
                    except Exception as e:
                        print(f"[ProgressManager] Cleanup error: {e}")
                self._generator_stack.pop()
                if self._overlay:
                    self._overlay._tag_redraw()
                return {"RUNNING_MODAL"}
            except Exception as e:
                # Generator error during cancel - still call cleanup
                if cleanup:
                    try:
                        cleanup("cancel")
                    except Exception as ce:
                        print(f"[ProgressManager] Cleanup error: {ce}")
                self._generator_stack.pop()
                if self._overlay:
                    self._overlay._tag_redraw()
                return {"RUNNING_MODAL"}

        # If we have pending tasks to execute
        if self._pending_execute:
            return self._execute_current_task(context)

        # Try to advance generator
        if not self._generator_stack:
            return self._complete(context)

        gen, cleanup = self._generator_stack[-1]
        try:
            cmd = next(gen)
            self._process_command(cmd)
            return {"RUNNING_MODAL"}
        except StopIteration:
            # Current generator exhausted - call its cleanup
            if cleanup:
                try:
                    cleanup(self._completion_reason)
                except Exception as e:
                    print(f"[ProgressManager] Cleanup error: {e}")
                    traceback.print_exc()

            self._generator_stack.pop()

            if not self._generator_stack:
                # All generators done - check if we have pending tasks
                if self._current_task_index < len(self._queue):
                    # Still have tasks to execute
                    self._pending_execute = True
                    if self._overlay:
                        self._overlay._tag_redraw()
                    return {"RUNNING_MODAL"}
                return self._complete(context)
            
            if self._overlay:
                self._overlay._tag_redraw()
            return {"RUNNING_MODAL"}

        except Exception as e:
            return self._handle_error(context, e)

    def _process_command(self, cmd) -> None:
        """Process a yield command from the generator."""
        if cmd is None:
            # Bare yield - just give UI a tick
            if self._overlay:
                self._overlay._tag_redraw()
            return

        # Use duck-typing instead of isinstance to handle class identity issues after hot reload
        # (generator may yield OLD_AddTask but we'd check against NEW_AddTask)
        cmd_type = type(cmd).__name__

        if cmd_type == "AddTask":
            task = cmd.task
            self._queue.add(task)
            if self._overlay:
                self._overlay._scroll_to_last_if_needed()
                self._overlay._tag_redraw()
            # Mark that we should execute on next tick
            self._pending_execute = True

        elif cmd_type == "ChainGenerator":
            # Push chained generator with its cleanup
            self._generator_stack.append((cmd.generator, cmd.on_cleanup))
            if self._overlay:
                self._overlay._tag_redraw()

    def _execute_current_task(self, context) -> Set[str]:
        """Execute the current pending task."""
        # Don't execute tasks if cancelled
        if self._cancelled:
            self._pending_execute = False
            return {"RUNNING_MODAL"}

        if self._current_task_index >= len(self._queue):
            self._pending_execute = False
            return {"RUNNING_MODAL"}

        task = self._queue[self._current_task_index]

        # First tick for this task: mark active
        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.ACTIVE
            if self._overlay:
                self._overlay.set_active_task(self._current_task_index)
            return {"RUNNING_MODAL"}

        # Second tick: execute
        self._task_start_time = time.perf_counter()

        try:
            result = task.execute(context)
            task.status = TaskStatus.DONE
            task.result = result if result else {"success": True}
            task.elapsed_seconds = time.perf_counter() - self._task_start_time

            if self._overlay:
                self._overlay.mark_task_done(
                    self._current_task_index,
                    result=task.result,
                    elapsed_seconds=task.elapsed_seconds,
                )

            self._current_task_index += 1

            # Check if more tasks or generators to process
            if self._current_task_index >= len(self._queue):
                self._pending_execute = False

            return {"RUNNING_MODAL"}

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.elapsed_seconds = time.perf_counter() - self._task_start_time
            task.result = {"success": False, "error": str(e)}
            return self._handle_error(context, e)

    def _complete(self, context) -> Set[str]:
        """Handle successful completion."""
        self._completion_reason = "success"

        # Count results
        failed_count = self._queue.count_by_status(TaskStatus.FAILED)

        if failed_count > 0:
            msg = f"Completed with {failed_count} failures."
        else:
            msg = "Successfully completed!"

        if self._overlay:
            self._overlay.set_completed(msg)

        self._awaiting_confirmation = True
        self._stop_timer(context)
        return {"RUNNING_MODAL"}

    def _handle_error(self, context, error: Exception) -> Set[str]:
        """Handle an error during execution."""
        self._completion_reason = "error"
        self._error_message = str(error)

        print(f"[ProgressManager] Error: {error}")
        traceback.print_exc()

        # Call all remaining cleanups with error reason
        while self._generator_stack:
            _, cleanup = self._generator_stack.pop()
            if cleanup:
                try:
                    cleanup("error")
                except Exception as e:
                    print(f"[ProgressManager] Cleanup error during error handling: {e}")

        if self._overlay:
            self._overlay.set_error(str(error)[:100])

        self._awaiting_confirmation = True
        self._stop_timer(context)
        return {"RUNNING_MODAL"}

    def _handle_cancel(self, context) -> None:
        """Handle user cancellation (ESC)."""
        self._completion_reason = "cancel"
        self._cancelled = True

        # Mark remaining tasks as cancelled
        if self._queue:
            self._queue.mark_remaining_cancelled()

        # Don't pop generators here - let them finish naturally in _tick()
        # They'll be cleaned up as they finish with "cancel" reason

        if self._overlay:
            self._overlay.set_cancelled("Cancelled.")

        self._awaiting_confirmation = True
        self._stop_timer(context)

    def _finish(self, context) -> None:
        """Finish the operation and clean up."""
        # Stop timer if still running
        self._stop_timer(context)

        # Finish overlay
        if self._overlay:
            self._overlay.finish()
            self._overlay = None

        # Call any remaining cleanups (shouldn't be any normally, but safety)
        cleanup_count = 0
        while self._generator_stack:
            _, cleanup = self._generator_stack.pop()
            if cleanup:
                cleanup_count += 1
                try:
                    cleanup(self._completion_reason)
                except Exception as e:
                    print(f"[ProgressManager] Cleanup error in _finish: {e}")
                    traceback.print_exc()

        # Reset state
        self._is_running = False
        self._generator_stack = []
        self._queue = None
        self._context = None
        self._awaiting_confirmation = False
        self._cancelled = False

        # Clear singleton so next operation gets a fresh manager
        ProgressManager._instance = None

    def _stop_timer(self, context) -> None:
        """Stop the timer if running."""
        if self._timer and context and context.window_manager:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
