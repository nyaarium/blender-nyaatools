---
name: development
description: Provides development tools and guidance. Use when developing code, debugging, or running anything in the development environment.
---

# Development

## Technology Stack

- Blender addon (Python)
- Code in WSL; Blender runs on Windows

## Development Guidelines

Use the language server and project linters where available.

## Deploying Changes

Command: `./dev_deploy.sh | grep ".py"`

After making changes:

1. Auto-run the command to deploy to Blender.
2. Delete old logs to reduce bloat.
3. Inform the user to reload the addon.

## Debugging Across Windows/WSL Filesystem Boundaries

Blender runs on Windows, code workspace is in WSL.

### Write Diagnostics from Windows into WSL

In Blender Python, write diagnostics to the workspace via the WSL network path so the agent can read them on Linux. Use `\\wsl$\Ubuntu-24.04\`.

```python
# Example: write to project .cursor/debug-{sessionId}.log from Blender on Windows
import os
log_path = r"\\wsl$\Ubuntu-24.04\home\nyaarium\blender-nyaatools\.cursor\debug-" + os.environ.get("DEBUG_SESSION_ID", "default") + ".log"
with open(log_path, "a", encoding="utf-8") as f:
    f.write(...)
```

## Debugging Approach

When debugging issues, follow this systematic approach to avoid drowning the codebase in unnecessary logging.

### 1. Hypothesize First

Before adding any instrumentation, state 3-5 concrete, testable hypotheses. Good ones are specific and testable (e.g. "the auth token is null at checkout" or "the loop uses `count < 10` instead of `count <= 10`"). Avoid vague statements ("something is broken in the payment flow").

### 2. Instrument to Test Hypotheses

Add write calls from Blender Python to `.cursor/debug-{sessionId}.log` (via the WSL network path below) to confirm or reject each hypothesis (typically 2-6 logs total). Log entry/exit, key values at decision points, which branch was taken, and important return values. Don't log every line, redundant data, or things you already know are correct.

### 3. Gather Evidence

Run the code and examine the debug log. For each hypothesis, decide:

- **CONFIRMED** - The logs prove this is the issue
- **REJECTED** - The logs prove this is NOT the issue
- **INCONCLUSIVE** - Need different instrumentation to test this

Only fix issues when you have clear runtime evidence pointing to the cause. Don't guess.

### 4. Fix and Verify

Keep instrumentation in place after a fix, run a verification test, and only remove debug logs once the fix is confirmed. That avoids "fixed one thing, broke another."

## Writing to the Debug Log from Blender

Blender runs on Windows; the workspace is in WSL. Write diagnostics to the workspace via the WSL network path so the agent can read `.cursor/debug-{sessionId}.log` on Linux.

**Path (from Blender on Windows):** `\\wsl$\Ubuntu-24.04\home\nyaarium\blender-nyaatools\.cursor\debug-{sessionId}.log`

**Format:** One JSON object per line (NDJSON). Each line must include **id**, **timestamp** (ms since Unix epoch), **location**, **message**, **data** (object). Optional: **hypothesisId**, **runId**. You must supply `id` yourself (e.g. `log_{timestamp}_{random}`).

### Example

```python
import json
import os
import time
import random
import string

DEBUG_LOG = r"\\wsl$\Ubuntu-24.04\home\nyaarium\blender-nyaatools\.cursor\debug-" + os.environ.get("DEBUG_SESSION_ID", "default") + ".log"

def _log_id():
    return "log_%d_%s" % (int(time.time() * 1000), "".join(random.choices(string.ascii_lowercase + string.digits, k=8)))

# #region agent log
with open(DEBUG_LOG, "a", encoding="utf-8") as f:
    f.write(json.dumps({
        "id": _log_id(),
        "timestamp": int(time.time() * 1000),
        "location": "operators/export_vrm.py:142",
        "message": "Checking mesh before export",
        "hypothesisId": "A",
        "data": {
            "mesh_count": len(meshes),
            "has_armature": armature is not None,
        },
    }, ensure_ascii=False) + "\n")
# #endregion
```

## GitHub Workflow Tips

If you need to check a Github workflow runner job's log, you can use the `gh` CLI:

- Ask for one of either:
  - URL. Route must contain: `*/actions/runs/*`
  - Run ID or Job ID. If the ID is 5 char or less, assume it's wrong; There is a shorter human friendly ID on the website <=5 chars.
- View it with:
  - `gh run view $RUN_ID --log`
  - `gh run view --log-failed --job=$JOB_ID`
