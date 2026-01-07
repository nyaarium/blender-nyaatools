---
name: Blender Development
description: Skills for Blender development
---

# Blender Development

## Deploying Changes

Command: `./dev_deploy.sh | grep ".py"`

After making changes, run the command to deploy to Blender. Inform the user to reload the addon after calling it.

## Windows/WSL File System Split

Blender runs on Windows, workspace is in WSL.

When writing diagnostics data, write as if running on Windows, to %TEMP%.
Then as the agent, you can read the diagnostics data from as if running on WSL.

**Python code reads/writes to Windows %TEMP%:**
```python
# Writes to: C:\Users\{username}\AppData\Local\Temp\...
log_path = os.path.join(tempfile.gettempdir(), ...)
```

**Agent tools read from WSL mount:**

Tools like `read_file` and `grep` can be used to read from: `/mnt/c/Users/{username}/AppData/Local/Temp/...`
