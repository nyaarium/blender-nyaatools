"""
Bake pipeline module.

This module contains the refactored baking system with proper multi-mesh support.
"""

from .bake_context import (
    BakeContext,
    MeshMeta,
    BakeImageConfig,
    set_pending_bake_context,
    get_pending_bake_context,
    clear_pending_bake_context,
    has_pending_bake_context,
)
from .bake_prepare import prepare_meshes_for_baking
from .bake_execute import execute_bake_for_material

__all__ = [
    "BakeContext",
    "MeshMeta",
    "BakeImageConfig",
    "set_pending_bake_context",
    "get_pending_bake_context",
    "clear_pending_bake_context",
    "has_pending_bake_context",
    "prepare_meshes_for_baking",
    "execute_bake_for_material",
]
