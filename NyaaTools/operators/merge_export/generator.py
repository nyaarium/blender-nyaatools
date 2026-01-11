"""
Merge & Export generator for chainable operations.

This module provides a reusable generator function that can be used by
the standalone operator or chained from a batch operator.
"""

import bpy
import os
import math

from dataclasses import dataclass, field
from typing import Callable, Dict, Generator, List, Optional, Any
from mathutils import Euler


from ..bake.generator import create_bake_generator, BakeState
from ...common.resolve_path import resolve_path
from ...common.file_stuff import sanitize_name
from ...common.renamer_restore import renamer_restore
from ...common.resolve_path import resolve_path
from ...bake.bake_context import BakeContext, BakeImageConfig, MeshMeta
from ...ui.task_system import Task, TaskStatus, DrawHelper, LINE_HEIGHT, FONT_SIZE_BODY
from ...ui.ProgressManager import AddTask, ChainGenerator

from ...asset.asset_lookup import get_export_path_from_asset
from ...asset.merge_layers import (
    merge_single_layer,
    copy_armature_to_collection,
    get_asset_non_collider_meshes_by_layer,
    process_collider_meshes,
)
from ...common.deselect_all import deselect_all
from ...common.selection_add import selection_add
from ...asset.export_votv import render_votv_icon, export_votv
from ...asset.export_collection import (
    get_or_create_export_collection,
    clear_export_collection,
    ensure_collection_accessible,
    set_collection_visibility,
    get_textures_directory,
    create_baked_material,
)


TEMP_SCENE_NAME = "Temp Merge & Export"

# Column widths for merge/export task rendering
MERGE_EXPORT_COL_WIDTH_STATUS = 100  # Status column
MERGE_EXPORT_COL_WIDTH_TIME = 80  # Time column
MERGE_EXPORT_COL_WIDTH_NAME = 250  # Asset name column
MERGE_EXPORT_COL_WIDTH_FORMAT = 150  # Format type column (FBX, OBJ, VOTV)
MERGE_EXPORT_COL_WIDTH_PATH = 500  # Export path column

MERGE_COL_WIDTH_LAYER = 250  # Layer name column (for merge tasks)
MERGE_COL_WIDTH_MESH_COUNT = 100  # Mesh count column (for merge tasks)
MERGE_COL_WIDTH_DETAILS = 400  # Details column (for merge tasks)


def render_merge_row(task: Task, x: int, y: int, draw: DrawHelper) -> int:
    """
    Custom render for merge task rows.

    Format: [Status] [Time] [Layer Name] [Details]
    """
    params = task.params
    col_x = x

    # Status column (fixed width)
    status_color = draw.get_status_color(task.status)
    status_text = draw.get_status_text(task.status)
    draw.draw_text(status_text, col_x, y, FONT_SIZE_BODY, status_color)
    col_x += MERGE_EXPORT_COL_WIDTH_STATUS

    # Time column (fixed width, always show)
    time_text = draw.format_seconds(task.elapsed_seconds)
    draw.draw_text(time_text, col_x, y, FONT_SIZE_BODY, status_color)
    col_x += MERGE_EXPORT_COL_WIDTH_TIME

    # Layer name column (fixed width)
    layer_name = params.get("layer_name", "")
    draw.draw_text(layer_name, col_x, y, FONT_SIZE_BODY, draw.COLOR_TEXT)
    col_x += MERGE_COL_WIDTH_LAYER

    # Details column (fixed width, grey)
    mesh_count = params.get("mesh_count", 0)
    shape_key_count = params.get("shape_key_count", 0)
    total_applications = params.get("total_applications", 0)

    details_parts = []
    details_parts.append(f"{mesh_count} meshes")
    details_parts.append(f"{shape_key_count} shape keys")
    details_parts.append(f"{total_applications} total to apply")

    details_text = "    ".join(details_parts)
    draw.draw_text(details_text, col_x, y, FONT_SIZE_BODY, draw.COLOR_TEXT_DIM)

    return LINE_HEIGHT


def render_export_row(task: Task, x: int, y: int, draw: DrawHelper) -> int:
    """
    Custom render for export task rows.

    Format: [Status] [Time] [Asset Name] [Format] [Export Path]
    """
    params = task.params
    col_x = x

    # Status column (fixed width)
    status_color = draw.get_status_color(task.status)
    status_text = draw.get_status_text(task.status)
    draw.draw_text(status_text, col_x, y, FONT_SIZE_BODY, status_color)
    col_x += MERGE_EXPORT_COL_WIDTH_STATUS

    # Time column (fixed width, always show)
    time_text = draw.format_seconds(task.elapsed_seconds)
    draw.draw_text(time_text, col_x, y, FONT_SIZE_BODY, status_color)
    col_x += MERGE_EXPORT_COL_WIDTH_TIME

    # Asset name column (fixed width)
    asset_name = params.get("asset_name", "")
    draw.draw_text(asset_name, col_x, y, FONT_SIZE_BODY, draw.COLOR_TEXT)
    col_x += MERGE_EXPORT_COL_WIDTH_NAME

    # Format type column (fixed width, grey)
    format_type = params.get("format_type", "")
    draw.draw_text(format_type, col_x, y, FONT_SIZE_BODY, draw.COLOR_TEXT_DIM)
    col_x += MERGE_EXPORT_COL_WIDTH_FORMAT

    # Export path column (fixed width, grey)
    export_path = params.get("export_path", "")
    clean_asset_name = params.get("clean_asset_name")
    # Only append clean_asset_name if it exists (VotV format only)
    # if clean_asset_name: # DEBUG STOP
    export_path = export_path + clean_asset_name + "/"
    draw.draw_text(export_path, col_x, y, FONT_SIZE_BODY, draw.COLOR_TEXT_DIM)

    return LINE_HEIGHT


def _votv_filename_formatter(mat_name, dtp_format, ext):
    """Format filename for VotV baked textures."""
    votv_format_map = {
        "rgba": "diffuse",
        "me-sp-ro": "pbr",
        "normalgl": "normal",
        "emission": "emissive",
    }
    if dtp_format in votv_format_map:
        return f"{votv_format_map[dtp_format]}_{mat_name}.png"
    return f"{mat_name}.{dtp_format}.{ext}"


# =============================================================================
# Config and State
# =============================================================================


@dataclass
class MergeExportConfig:
    """Immutable configuration for merge & export operation."""

    asset_host: Any  # bpy.types.Object (armature or mesh)
    asset_name: str
    export_format: str  # "fbx", "obj", "votv"
    target_type: str  # "file" or "collection"
    export_static: bool
    bake_after_export: bool
    include_ue_colliders: bool


@dataclass
class MergeExportState:
    """Mutable state for tracking merge & export progress."""

    temp_scene: Any = None  # bpy.types.Scene
    original_scene: Any = None  # bpy.types.Scene
    armature_copy: Any = None  # bpy.types.Object
    merged_layers: Dict[str, Any] = field(default_factory=dict)
    collider_objects: List[Any] = field(default_factory=list)
    unrename_info: List = field(default_factory=list)
    export_path: str = ""
    treat_as_static: bool = False
    mesh_names: List[str] = field(default_factory=list)
    export_collection: Any = None  # bpy.types.Collection
    textures_dir: str = ""
    # Will be set if bake is chained
    bake_state: Any = None  # BakeState from bake generator


# =============================================================================
# Generator
# =============================================================================


def create_merge_export_generator(
    config: MergeExportConfig,
    state: MergeExportState,
    debug_print: Optional[Callable] = None,
) -> Generator:
    """
    Create a generator that yields merge & export tasks.

    Args:
        config: Immutable configuration
        state: Mutable state for tracking progress
        debug_print: Optional debug print function

    Yields:
        AddTask and ChainGenerator commands
    """
    if debug_print is None:

        def debug_print(*args):
            print("   ", *args)

    asset_host = config.asset_host
    include_colliders = config.include_ue_colliders or config.export_format == "votv"

    # Get layers to merge
    asset_meshes_layers = get_asset_non_collider_meshes_by_layer(asset_host)
    layer_names = list(asset_meshes_layers.keys())

    # Yield merge tasks
    for layer_name in layer_names:
        layer_meshes = asset_meshes_layers[layer_name]
        mesh_count = len(layer_meshes)

        # Count shape keys and modifiers per mesh, calculate total applications
        total_shape_keys = 0
        total_applications = 0
        for mesh_obj in layer_meshes.values():
            if mesh_obj.type == "MESH":
                # Count shape keys for this mesh
                mesh_shape_keys = 0
                if mesh_obj.data.shape_keys:
                    mesh_shape_keys = len(mesh_obj.data.shape_keys.key_blocks)
                total_shape_keys += mesh_shape_keys

                # Count modifiers that will be applied (exclude armature for rigged exports)
                modifier_count = 0
                for mod in mesh_obj.modifiers:
                    if config.export_static or mod.type != "ARMATURE":
                        modifier_count += 1

                # Total applications = shape_keys * modifiers for this mesh
                total_applications += mesh_shape_keys * modifier_count

        # Capture for closure
        ln = layer_name
        lm = layer_meshes

        yield AddTask(
            Task(
                id=f"merge_{layer_name}",
                label=f"Merge: {layer_name} ({mesh_count} meshes)",
                execute=lambda ctx, ln=ln, lm=lm: _do_merge(
                    config, state, ln, lm, debug_print
                ),
                render_row=render_merge_row,
                params={
                    "layer_name": layer_name,
                    "mesh_count": mesh_count,
                    "shape_key_count": total_shape_keys,
                    "total_applications": total_applications,
                },
            )
        )

    # Yield export task based on target type
    if config.target_type == "collection":
        yield AddTask(
            Task(
                id="export_collection",
                label="Export to __Export__ collection",
                execute=lambda ctx: _do_export_collection(
                    config, state, include_colliders, debug_print
                ),
                render_row=render_export_row,
                params={
                    "asset_name": config.asset_name,
                    "format_type": "COLLECTION",
                    "export_path": "__Export__",
                },
            )
        )
    else:
        export_path_display = ""
        if state.export_path:
            export_path_display = state.export_path

        # VotV: Sanitize asset name for subfolder
        clean_asset_name = None
        if config.export_format == "votv":
            clean_asset_name = sanitize_name(config.asset_name, strict=True)

        yield AddTask(
            Task(
                id="export_file",
                label=f"Export: {config.asset_name}",
                execute=lambda ctx: _do_export_file(
                    config, state, include_colliders, debug_print
                ),
                render_row=render_export_row,
                params={
                    "asset_name": config.asset_name,
                    "clean_asset_name": clean_asset_name,
                    "format_type": config.export_format.upper(),
                    "export_path": export_path_display,
                },
            )
        )

    # Chain to bake if requested
    if config.bake_after_export:
        bake_ctx, bake_cleanup = _create_bake_context(config, state, debug_print)
        state.bake_state = BakeState()

        yield ChainGenerator(
            generator=create_bake_generator(bake_ctx, state.bake_state, debug_print),
            on_cleanup=bake_cleanup,
        )


# =============================================================================
# Task Executors
# =============================================================================


def _do_merge(
    config: MergeExportConfig,
    state: MergeExportState,
    layer_name: str,
    layer_meshes: List,
    debug_print: Callable,
) -> Dict:
    """Execute a single layer merge."""
    merged_obj, unrename = merge_single_layer(
        layer_name,
        layer_meshes,
        state.temp_scene.collection,
        armature_copy=state.armature_copy,
        is_static_export=config.export_static,
        debug_print=debug_print,
    )
    if merged_obj:
        state.merged_layers[layer_name] = merged_obj
    state.unrename_info.extend(unrename)
    return {"success": True}


def _do_export_file(
    config: MergeExportConfig,
    state: MergeExportState,
    include_colliders: bool,
    debug_print: Callable,
) -> Dict:
    """Execute file export (FBX, OBJ, VotV)."""
    # Process colliders if requested
    if include_colliders:
        collider_objs, collider_unrename = process_collider_meshes(
            config.asset_host, state.temp_scene.collection, debug_print
        )
        state.collider_objects.extend(collider_objs)
        state.unrename_info.extend(collider_unrename)

    # Remove armature if exporting static (modifiers already applied early)
    if config.export_static and state.armature_copy:
        bpy.data.objects.remove(state.armature_copy, do_unlink=True)
        debug_print("Removed armature for static export")
        state.armature_copy = None

    # Capture mesh names before export
    state.mesh_names = [
        obj.name for obj in state.merged_layers.values() if obj.type == "MESH"
    ]

    # Perform export
    _finalize_and_export(
        config.asset_name,
        state.armature_copy,
        state.export_path,
        config.export_format,
        state.unrename_info,
        state.treat_as_static,
        state.temp_scene,
        debug_print,
    )

    return {"success": True, "file_path": state.export_path}


def _do_export_collection(
    config: MergeExportConfig,
    state: MergeExportState,
    include_colliders: bool,
    debug_print: Callable,
) -> Dict:
    """Execute collection export - move merged objects to __Export__ collection."""
    # Process colliders if requested
    if include_colliders:
        collider_objs, collider_unrename = process_collider_meshes(
            config.asset_host, state.temp_scene.collection, debug_print
        )
        state.collider_objects.extend(collider_objs)
        state.unrename_info.extend(collider_unrename)

    # Remove armature if exporting static (modifiers already applied early)
    if config.export_static and state.armature_copy:
        bpy.data.objects.remove(state.armature_copy, do_unlink=True)
        debug_print("Removed armature for static export")
        state.armature_copy = None

    # Move objects from temp scene to export collection
    exported_objects = []
    for obj in list(state.temp_scene.collection.objects):
        state.temp_scene.collection.objects.unlink(obj)
        state.export_collection.objects.link(obj)
        exported_objects.append(obj)

    # Capture mesh names
    state.mesh_names = [obj.name for obj in exported_objects if obj.type == "MESH"]

    # Mark as Blender asset (don't mark colliders as assets)
    collider_names = {obj.name for obj in state.collider_objects}

    if state.armature_copy and not state.treat_as_static:
        # For rigged assets, mark the armature
        state.armature_copy.asset_mark()
        state.armature_copy.asset_generate_preview()
        debug_print(f"✅ Marked as asset: {state.armature_copy.name}")
    else:
        # For static exports, mark each mesh (except colliders)
        for obj in exported_objects:
            if obj.type == "MESH" and obj.name not in collider_names:
                obj.asset_mark()
                obj.asset_generate_preview()
                debug_print(f"✅ Marked as asset: {obj.name}")

    return {"success": True, "object_count": len(exported_objects)}


# =============================================================================
# Bake Integration
# =============================================================================


def _create_bake_context(
    config: MergeExportConfig,
    state: MergeExportState,
    debug_print: Callable,
):
    """Create bake context and cleanup for the bake generator."""
    cfg = config.asset_host.nyaa_asset

    # Determine bake directory based on target type
    if config.target_type == "collection":
        bake_dir = state.textures_dir
    else:
        export_path = state.export_path
        if export_path:
            if config.export_format == "votv":
                clean_asset_name = sanitize_name(config.asset_name, strict=True)
                if export_path.endswith(clean_asset_name):
                    bake_dir = export_path
                else:
                    bake_dir = os.path.join(export_path, clean_asset_name)
            else:
                bake_dir = os.path.join(
                    os.path.dirname(resolve_path(export_path, "temp")), "textures"
                )
        else:
            blend_dir = (
                os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd()
            )
            bake_dir = os.path.join(blend_dir, "textures")

    # Get mesh list for baking
    mesh_names = state.mesh_names if state.mesh_names else []

    # For VotV file export, find the merged object
    if config.target_type == "file" and config.export_format == "votv":
        clean_asset_name = sanitize_name(config.asset_name, strict=True)
        merged_obj = None
        for obj in state.temp_scene.objects:
            if obj.type == "MESH" and obj.name == clean_asset_name:
                merged_obj = obj
                break
        if merged_obj:
            mesh_objects = [merged_obj]
            mesh_names = [merged_obj.name]
        else:
            debug_print(f"⚠️ Could not find merged VotV object '{clean_asset_name}'")
            mesh_objects = []
    else:
        # Find mesh objects by name
        mesh_objects = []
        for mesh_name in mesh_names:
            obj = bpy.data.objects.get(mesh_name)
            if obj and obj.type == "MESH":
                mesh_objects.append(obj)

    # Build mesh metas
    mesh_metas = [
        MeshMeta(mesh_object=obj, layer_name="", is_ue_collider=False)
        for obj in mesh_objects
    ]

    # Convert bake image configs
    bake_configs = [
        BakeImageConfig(
            format=img.format,
            image_type=img.image_type,
            width=int(img.width),
            height=int(img.height),
            optimize_resolution=img.optimize_resolution,
        )
        for img in cfg.bake_images
    ]

    # Filename formatter for VotV
    filename_formatter = None
    if config.target_type == "file" and config.export_format == "votv":
        filename_formatter = _votv_filename_formatter

    # Create bake context
    bake_ctx = BakeContext(
        mesh_metas=mesh_metas,
        bake_images=bake_configs,
        export_dir=bake_dir,
        filename_formatter=filename_formatter,
        save_to_file=True,
        wait_for_enter=False,
    )

    # Capture for cleanup lambda
    tex_dir = bake_dir
    target_type = config.target_type
    export_collection = state.export_collection
    captured_mesh_names = mesh_names

    def bake_cleanup(reason):
        """Cleanup after bake completes."""
        debug_print(f"[Bake cleanup] reason={reason}")

        # Assign baked materials
        for mesh_name in captured_mesh_names:
            obj = bpy.data.objects.get(mesh_name)
            if obj and obj.type == "MESH":
                for slot in obj.material_slots:
                    if slot.material:
                        baked_mat = create_baked_material(slot.material, tex_dir)
                        if baked_mat:
                            slot.material = baked_mat
                            debug_print(f"🎨 Assigned baked material: {baked_mat.name}")

        # Hide export collection (for collection export)
        if target_type == "collection" and export_collection:
            set_collection_visibility(export_collection, hide=True, hide_render=True)

    debug_print(f"🍞 Baking setup for {len(mesh_objects)} merged meshes")
    return bake_ctx, bake_cleanup


# =============================================================================
# Setup and Cleanup Helpers
# =============================================================================


def setup_merge_export(
    config: MergeExportConfig,
    state: MergeExportState,
    debug_print: Optional[Callable] = None,
) -> bool:
    """
    Set up the merge & export operation (create temp scene, copy armature, etc).

    Call this BEFORE starting the generator.

    Returns:
        True if setup succeeded, False otherwise
    """
    if debug_print is None:

        def debug_print(*args):
            print("   ", *args)

    asset_host = config.asset_host

    # Compute derived state
    state.treat_as_static = asset_host.type == "MESH" or config.export_static
    state.export_path = get_export_path_from_asset(asset_host)
    state.unrename_info = []
    state.merged_layers = {}
    state.collider_objects = []
    state.mesh_names = []
    state.export_collection = None
    state.textures_dir = ""
    state.bake_state = None

    # Ensure object mode
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.outliner.orphans_purge(do_recursive=True)

    # For collection export, set up the export collection
    if config.target_type == "collection":
        state.export_collection = get_or_create_export_collection()
        clear_export_collection()
        ensure_collection_accessible(state.export_collection)
        state.textures_dir = get_textures_directory(asset_host)

    # Render VotV icon before modifying scene (file export only)
    if config.target_type == "file" and config.export_format == "votv":
        render_votv_icon(asset_host, config.asset_name, debug_print)

    # Create temporary scene
    temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
    if temp_scene:
        bpy.data.scenes.remove(temp_scene, do_unlink=True)
        bpy.ops.outliner.orphans_purge(do_recursive=True)

    state.temp_scene = bpy.data.scenes.new(name=TEMP_SCENE_NAME)
    state.original_scene = bpy.context.window.scene

    # Focus viewport on asset meshes in main scene, then copy viewport angle to temp scene
    _setup_viewport_from_main_scene(asset_host, state.temp_scene, state.original_scene)

    bpy.context.window.scene = state.temp_scene

    # For armature-based assets, copy armature to temp scene
    if not state.treat_as_static or asset_host.type == "ARMATURE":
        state.armature_copy, arm_unrename = copy_armature_to_collection(
            asset_host,
            state.temp_scene.collection,
            (
                "Armature"
                if config.target_type == "file"
                else asset_host.nyaa_asset.asset_name
            ),
            debug_print,
        )
        state.unrename_info.extend(arm_unrename)

    return True


def cleanup_merge_export(
    config: MergeExportConfig,
    state: MergeExportState,
    reason: str,
    debug_print: Optional[Callable] = None,
) -> str:
    """
    Clean up after merge & export operation.

    Args:
        config: The operation config
        state: The operation state
        reason: 'success', 'error', or 'cancel'
        debug_print: Optional debug print function

    Returns:
        A message describing the result
    """
    if debug_print is None:

        def debug_print(*args):
            print("   ", *args)

    debug_print(f"[MergeExport cleanup] reason={reason}")

    if config.target_type == "collection":
        return _cleanup_collection_export(config, state, reason)
    else:
        return _cleanup_file_export(config, state, reason)


def _cleanup_file_export(
    config: MergeExportConfig,
    state: MergeExportState,
    reason: str,
) -> str:
    """Clean up after file export."""
    _cleanup_scene(state)

    if reason == "success":
        path = state.export_path
        if path:
            path = resolve_path(path, config.asset_name)
        bake_msg = ""
        if state.bake_state:
            bake_msg = f" Baked {state.bake_state.baked_count} textures."
        return f"Export successful!{bake_msg}  " + (path or "")
    elif reason == "cancel":
        return "Export cancelled."
    else:
        return "Export failed."


def _cleanup_collection_export(
    config: MergeExportConfig,
    state: MergeExportState,
    reason: str,
) -> str:
    """Clean up after collection export."""
    # Restore original scene
    if state.original_scene and state.original_scene.name in bpy.data.scenes:
        bpy.context.window.scene = state.original_scene

    # Remove temp scene
    temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
    if temp_scene:
        bpy.data.scenes.remove(temp_scene, do_unlink=True)
        bpy.ops.outliner.orphans_purge(do_recursive=True)

    # Restore renamed objects
    if state.unrename_info:
        renamer_restore(state.unrename_info)

    # Handle based on reason
    if state.export_collection:
        if reason == "success":
            # Collection visibility is handled by bake_cleanup if baking,
            # otherwise hide here
            if not config.bake_after_export:
                set_collection_visibility(
                    state.export_collection, hide=True, hide_render=True
                )
            object_count = len(state.mesh_names) if state.mesh_names else 0
            bake_msg = ""
            if state.bake_state:
                bake_msg = f" Baked {state.bake_state.baked_count} textures."
            return (
                f"Exported to __Export__ collection ({object_count} objects).{bake_msg}"
            )
        else:
            # On cancel/error, clear the collection
            clear_export_collection()
            if reason == "cancel":
                return "Export cancelled."
            return "Export failed."
    return ""


def _cleanup_scene(state: MergeExportState) -> None:
    """Clean up the temporary scene."""
    temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
    if temp_scene:
        if state.original_scene and state.original_scene.name in bpy.data.scenes:
            bpy.context.window.scene = state.original_scene
        bpy.data.scenes.remove(temp_scene, do_unlink=True)
        bpy.ops.outliner.orphans_purge(do_recursive=True)
        if state.unrename_info:
            renamer_restore(state.unrename_info)


def _setup_viewport_from_main_scene(
    asset_host: Any,
    temp_scene: Any,
    original_scene: Any,
) -> None:
    """
    Focus viewport on asset meshes in main scene, capture viewport angle,
    apply it to temp scene, then restore main scene viewport.

    Steps:
    1. Select all asset layer meshes in main scene
    2. Focus and angle viewport in main scene (remember original)
    3. Apply viewport angle to temp scene
    4. Restore main scene viewport angle
    """
    # Get asset layer meshes
    asset_meshes_layers = get_asset_non_collider_meshes_by_layer(asset_host)

    # Collect all meshes from all layers
    meshes_to_select = []
    for layer_meshes in asset_meshes_layers.values():
        meshes_to_select.extend(layer_meshes.values())

    if not meshes_to_select:
        return

    # Store original scene context
    original_active = bpy.context.active_object
    original_selected = list(bpy.context.selected_objects)

    # Switch to main scene if needed
    if bpy.context.scene != original_scene:
        bpy.context.window.scene = original_scene

    # Ensure object mode
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    # Select all asset meshes in main scene
    deselect_all()
    first_obj = None
    for mesh_obj in meshes_to_select:
        if mesh_obj and mesh_obj.name in bpy.data.objects:
            selection_add(mesh_obj)
            if first_obj is None:
                first_obj = mesh_obj

    if not first_obj:
        return

    # Store original viewport rotations for all 3D viewports
    original_view_rotations = {}
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                rv3d = area.spaces.active.region_3d
                if rv3d:
                    # Store by window/area for restoration
                    key = (window, area)
                    original_view_rotations[key] = rv3d.view_rotation.copy()

    # Focus viewport on selected meshes in main scene
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                rv3d = area.spaces.active.region_3d
                if rv3d:
                    region = None
                    for r in area.regions:
                        if r.type == "WINDOW":
                            region = r
                            break

                    if region:
                        with bpy.context.temp_override(
                            window=window, area=area, region=region
                        ):
                            bpy.ops.view3d.view_selected()

    # Capture the viewport rotation from main scene (use first 3D viewport)
    captured_rotation = None
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                rv3d = area.spaces.active.region_3d
                if rv3d:
                    captured_rotation = rv3d.view_rotation.copy()
                    break
        if captured_rotation:
            break

    # Restore main scene viewport rotations
    for (window, area), original_rot in original_view_rotations.items():
        rv3d = area.spaces.active.region_3d
        if rv3d:
            rv3d.view_rotation = original_rot

    # Restore main scene selection
    deselect_all()
    for obj in original_selected:
        if obj and obj.name in bpy.data.objects:
            selection_add(obj)
    if original_active and original_active.name in bpy.data.objects:
        bpy.context.view_layer.objects.active = original_active

    # Apply captured rotation to temp scene viewports
    if captured_rotation:
        # Switch to temp scene temporarily to apply rotation
        temp_context_scene = bpy.context.scene
        bpy.context.window.scene = temp_scene

        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    rv3d = area.spaces.active.region_3d
                    if rv3d:
                        rv3d.view_rotation = captured_rotation.copy()

        # Restore context scene
        bpy.context.window.scene = temp_context_scene


def _finalize_and_export(
    asset_name,
    armature,
    export_path,
    export_format,
    unrename_info,
    is_static_asset,
    temp_scene,
    debug_print,
):
    """Finalize merged meshes and export in requested format."""
    if not export_path:
        armature_name = armature.name if armature else asset_name
        raise Exception(f"Export path not found for: {armature_name}")

    if export_format == "fbx":
        export_name = (
            asset_name
            if is_static_asset
            else (armature.name if armature else asset_name)
        )
        path = resolve_path(export_path, export_name + ".fbx")
        os.makedirs(os.path.dirname(path), exist_ok=True)

        bpy.ops.export_scene.fbx(
            filepath=path,
            check_existing=False,
            filter_glob="*.fbx",
            use_active_collection=True,
            apply_scale_options="FBX_SCALE_UNITS",
            axis_forward="-Y",
            axis_up="Z",
            use_mesh_modifiers=False,
            mesh_smooth_type="FACE",
            add_leaf_bones=False,
            bake_anim=False,
        )

    elif export_format == "obj":
        export_name = (
            asset_name
            if is_static_asset
            else (armature.name if armature else asset_name)
        )
        path = resolve_path(export_path, export_name + ".obj")
        os.makedirs(os.path.dirname(path), exist_ok=True)

        bpy.ops.wm.obj_export(
            filepath=path,
            check_existing=False,
            filter_glob="*.obj",
        )

    elif export_format == "votv":
        export_votv(asset_name, temp_scene, export_path, unrename_info, debug_print)
