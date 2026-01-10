# ProgressManager Execution Flow

**Tasks**: Atomic units of logic (e.g., Merge, Export) with a lifecycle: `PENDING` -> `ACTIVE` -> `DONE`.

**Queue**: An ordered `TaskQueue` that stores tasks and allows dynamic additions during operation.

**Yields**: Generators `yield AddTask` to enqueue work, `yield ChainGenerator` for nesting, or `yield None` to skip a tick.

**Timer**: A 0.05s heartbeat (20 ticks/sec). This is the frequency at which the manager "pumps" its logic—advancing generators or moving tasks through the Split-Tick pipeline—whenever the main thread is free.

**Redraws**: Requested by the manager during a **Timer** tick. It uses `bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)` to "poke" the 3D Viewport. This is necessary because Blender won't redraw the viewport unless something (like a mouse move or a timer) explicitly tells it to, ensuring the overlay doesn't freeze when the user stops moving the mouse.

**Split-Tick**: A technique to ensure UI updates are visible. The manager uses two separate timer ticks for every task:
1. **Activation Tick**: Marks task as `ACTIVE` and forces a redraw. Returning control to Blender here allows the "Running" status to actually appear on screen.
2. **Execution Tick**: The actual work begins on this second tick. This prevents the "Heavy Hang" from blocking the UI update that just happened in the first tick.

## Operation Lifecycle

**Tick 1: Initialization**
- `ProgressManager.execute()` is called. 
- UI elements (Panels, Gizmos) are hidden.
- `ProgressOverlay` initializes with title and empty `TaskQueue`.
- Generator `create_merge_export_generator` is instantiated but not yet advanced.
- Internal modal operator starts; first `_tick` begins.

**Tick 2: Queue Task 0 (Merge Body)**
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
- Modal timer is removed; system waits for keyboard input.
