# ProgressManager Execution Flow

**Tasks**: Atomic units of logic (e.g., Merge, Export) with a lifecycle: `PENDING` -> `ACTIVE` -> `DONE`.

**Queue**: An ordered `TaskQueue` that stores tasks and allows dynamic additions during operation.

**Yields**: Generators `yield AddTask` to enqueue work, `yield ChainGenerator` for nesting, or `yield None` to skip a tick.

**Timer**: A 0.05s heartbeat (20 ticks/sec). This is the frequency at which the manager "pumps" its logic—advancing generators or moving tasks through the Split-Tick pipeline—whenever the main thread is free.

**Redraws**: Requested by the manager during a **Timer** tick via `ProgressOverlay._tag_redraw()`. During the `RUNNING` state, it uses `bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)` for aggressive updates during heavy processing. During confirmation states (`ERROR`, `COMPLETED`), it switches to standard `area.tag_redraw()` to allow animations while avoiding cursor flickering. This ensures the overlay doesn't freeze when the user stops moving the mouse.

**Unified Error Handling**: A "State Transition" system rather than a "Reaction" system.
1. **Error Deposit**: Errors from Tasks, Generators, or even Render callbacks call `_report_error(e)`. Flags the manager state (sets _pending_error, _error_occurred = True), but does not perform immediate cleanup.
2. **Sync Point**: At the start of every **Timer** tick, the manager checks for a pending error and transitions the UI to the frozen `ERROR` state if one exists.
3. **Deferred Cleanup**: Scene cleanup (via generator `on_cleanup` calls) is strictly deferred until the user presses **Enter** to close the overlay or **Pause Break** to dismiss and inspect the broken state.

## Operation Lifecycle

**Tick 1: Initialization**
- `ProgressManager.execute()` is called. 
- UI elements (Panels, Gizmos) are hidden.
- Internal state reset, `_pending_error` set to `None`.
- `ProgressOverlay` initializes.
- Generator `create_merge_export_generator` instantiated.
- Internal modal operator starts; first `_tick` begins.

**The Error Tick (Hypothetical Task/Render Failure)**
- **Error Occurs**: A task crashes or the draw handler throws an exception.
- **Error Reporting**: `_report_error(e)` is called. `_pending_error` is set and `_error_occurred` is set to `True`.
- **State Transition (Next Tick)**: `_tick` detects the pending error and calls `_transition_to_error_state()`.
- **Wait**: Manager sets `_awaiting_confirmation = True`. UI shows the error. The timer remains active to drive UI animations (e.g., pulsing key hints).
- **Inspection**: The scene remains exactly as it was during the failure.
- **Resolution**: User presses ENTER. `_finish` runs, popping generators and calling cleanups.

## Split-Tick Lifecycle
- `next(gen)` yields `AddTask(merge_Body)`.
- Task is added to the `TaskQueue`. `_pending_execute` set to `True`.
- `_tag_redraw()` ensures the overlay list updates to show the pending row.

**Tick 3: Task 0 Activation**
- `_execute_current_task` detects `merge_Body` is `PENDING`.
- Task status updated to `ACTIVE`.
- `_overlay.set_active_task(0)` updates the footer message.
- `_tag_redraw()` (with `redraw_timer`) forces the yellow status text to the screen.

**Tick 4: Task 0 Execution**
- `task.execute()` calls its lambda (e.g., `_do_merge` for **Body**).
- **HEAVY HANG**: The main thread freezes while Blender performs Boolean/Joins.
- On return: Status set to `DONE`, time recorded, `current_task_index` increments.
- Control returns to Blender.

**Tick 5: Queue Task 1 (Merge Face)**
- `next(gen)` yields `AddTask(merge_Face)`.
- `_tag_redraw()` adds the new row to the UI.

**Tick 6: Task 1 Activation**
- Task `merge_Face` status set to `ACTIVE`.
- `_overlay.set_active_task(1)` updates footer.
- `_tag_redraw()` forces immediate UI update.

**Tick 7: Task 1 Execution**
- **HEAVY HANG**: `_do_merge` for **Face**.
- On return: Status set to `DONE`, `current_task_index` increments.

**Tick 8: Queue Task 2 (Export File)**
- `next(gen)` yields `AddTask(export_file)`.
- `_tag_redraw()` adds the Export row.

**Tick 9: Task 2 Activation**
- Task `export_file` status set to `ACTIVE`.
- `_tag_redraw()` ensures the user sees the "Running" state.

**Tick 10: Task 2 Execution**
- **HEAVY HANG**: `_do_export_file` (calls FBX/OBJ/VOTV export).
- On return: Status set to `DONE`, `current_task_index` increments.

**Tick 11: Completion**
- `next(gen)` raises `StopIteration`.
- `_complete()` marks the state as `COMPLETED`.
- Overlay displays "Successfully completed! Press ENTER to close".
- System waits for keyboard input. The timer remains active to keep the UI "alive" with animations until the user confirms.
- **Resolution**: User presses ENTER. `_finish` runs, calling `_stop_timer`, popping generators, and calling cleanups.
