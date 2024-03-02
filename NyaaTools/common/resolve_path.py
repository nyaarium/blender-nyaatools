import os
import bpy
from pathlib import Path


def resolve_path(path, default_file_name="Export.fbx"):
    # Replace all slashes
    path = path.replace("\\", "/")

    file_path = ""
    file_name = ""

    # Get path parts
    if path.endswith(".fbx"):
        file_name = path.split("/")[-1]
        file_path = path[: -len(file_name) - 1]
    else:
        file_name = default_file_name
        file_path = path

    if len(file_path) == 0:
        file_path = "./"

    print(file_path)
    print(file_name)

    # A. Absolute paths (D:\Path)
    # B. Network path (\\Network Path)
    # C. Relative paths
    if 2 <= len(file_path) and file_path[1] == ":":
        path = file_path + "/" + file_name
    elif file_path.startswith("//"):
        path = file_path + "/" + file_name
    else:
        path = bpy.path.abspath("//" + file_path + "/" + file_name)

    resolved = Path(path).resolve()
    cleaned = os.path.abspath(resolved)
    return cleaned
