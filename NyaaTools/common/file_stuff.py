import os
import re
from pathlib import Path


def sanitize_name(name, strict=False):
    """
    Sanitize a name for safe file system usage.

    Args:
        name: The name to sanitize
        strict: If True, only allow alphanumeric, dash, underscore (for VotV).
                If False, only remove Windows-unsafe characters (default).

    Returns:
        Sanitized name string
    """
    if strict:
        # Strict mode: only alphanumeric, dash, underscore
        return re.sub(r"[^a-zA-Z0-9\-_]", "_", name)
    else:
        # Windows-safe mode: remove < > : " / \ | ? *
        return re.sub(r'[<>:"/\\|?*]', "_", name)


def deleteFile(os_path: str):
    """Delete a file/directory and recursively delete its empty parent directories.

    Args:
        os_path: OS path to the file. Relative, absolute, network path should work.
    """

    # Delete the file if it exists
    if os.path.exists(os_path):
        try:
            if os.path.isdir(os_path):
                os.rmdir(os_path)
            else:
                os.remove(os_path)
        except OSError as e:
            print(f"Error deleting file {os_path}: {e}")
            return

    # Try to remove empty parent directories recursively
    try:
        current_os_dir = Path(os_path).parent
        while current_os_dir.exists():
            if not any(current_os_dir.iterdir()):
                try:
                    current_os_dir.rmdir()
                    current_os_dir = current_os_dir.parent
                except OSError as e:
                    print(f"Error removing directory {current_os_dir}: {e}")
                    break
            else:
                break
    except OSError as e:
        print(f"Error accessing directory structure: {e}")
