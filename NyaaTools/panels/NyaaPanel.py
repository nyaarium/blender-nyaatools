"""
NyaaTools Panel - Unified Asset System.

Uses native Blender subpanels for collapsible sections.

Core Rule: The config host IS the asset identity:
- Has armature? Config lives on the Armature. Select armature to see asset.
- No armature? Config lives on the Mesh. Select mesh to see asset.

This file serves as the entry point and registration for all panel-related modules.
"""

import bpy
