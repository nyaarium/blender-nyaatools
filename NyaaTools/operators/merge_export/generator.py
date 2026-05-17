"""
Merge & Export generator for chainable operations.

This module provides a reusable generator function that can be used by
the standalone operator or chained from a batch operator.
"""

import bpy
import os
import math
import shutil
import tempfile

from dataclasses import dataclass, field
from typing import Callable, Dict, Generator, List, Optional, Any
from mathutils import Euler, Matrix


from ..bake.generator import create_bake_generator, BakeState
from ...common.resolve_path import resolve_path
from ...common.file_stuff import sanitize_name
from ...common.renamer_restore import renamer_restore
from ...common.resolve_path import resolve_path
from ...bake.bake_context import BakeContext, BakeImageConfig, MeshMeta
from ...ui.task_system import Task, TaskStatus, DrawHelper, LINE_HEIGHT, FONT_SIZE_BODY
from ...ui.ProgressManager import AddTask, ChainGenerator

from ...asset.asset_lookup import get_export_path_from_asset
from ...common.uv_projection import CollapsedUVFacesError
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
    if clean_asset_name:
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
    export_format: str  # "fbx", "glb", "obj", "votv"
    target_type: str  # "file" or "collection"
    export_static: bool
    bake_after_export: bool
    pack_textures_glb: bool
    axis_forward: str  # "+X", "-X", "+Y", "-Y", "+Z", "-Z" — Blender scene's forward
    axis_up: str  # "+X", "-X", "+Y", "-Y", "+Z", "-Z" — Blender scene's up
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
    # Set when a CollapsedUVFacesError fires: (original_mesh_name, face_indices)
    # Used by cleanup to re-select the bad faces on the original object after renames are restored.
    collapsed_uv_error: Optional[tuple] = None


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

    # Build export task (yielded later depending on bake ordering)
    if config.target_type == "collection":
        export_task = Task(
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
    else:
        export_path_display = ""
        if state.export_path:
            export_path_display = state.export_path

        # VotV: Sanitize asset name for subfolder
        clean_asset_name = None
        if config.export_format == "votv":
            clean_asset_name = sanitize_name(config.asset_name, strict=True)

        export_task = Task(
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

    # Pack mode: bake BEFORE export so glTF exporter embeds textures from materials
    if config.pack_textures_glb and config.target_type == "file":
        # Populate mesh_names early (normally done inside _do_export_file)
        state.mesh_names = [
            obj.name for obj in state.merged_layers.values() if obj.type == "MESH"
        ]

        bake_ctx, bake_cleanup = _create_bake_context(config, state, debug_print)
        state.bake_state = BakeState()

        yield ChainGenerator(
            generator=create_bake_generator(bake_ctx, state.bake_state, debug_print),
            on_cleanup=bake_cleanup,
        )
        yield AddTask(export_task)
    elif config.bake_after_export:
        yield AddTask(export_task)

        bake_ctx, bake_cleanup = _create_bake_context(config, state, debug_print)
        state.bake_state = BakeState()

        yield ChainGenerator(
            generator=create_bake_generator(bake_ctx, state.bake_state, debug_print),
            on_cleanup=bake_cleanup,
        )
    else:
        yield AddTask(export_task)


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
    try:
        merged_obj, _ = merge_single_layer(
            layer_name,
            layer_meshes,
            state.temp_scene.collection,
            armature_copy=state.armature_copy,
            is_static_export=config.export_static,
            debug_print=debug_print,
            out_unrename_info=state.unrename_info,
        )
    except CollapsedUVFacesError as e:
        # Store the original mesh name and bad face indices so cleanup can
        # re-select them on the original object after renames are restored.
        original_mesh_name = getattr(e, "original_mesh_name", None) or next(iter(layer_meshes))
        state.collapsed_uv_error = (original_mesh_name, e.face_indices)
        print(f"[MergeExport] Stored collapsed_uv_error: mesh='{original_mesh_name}', faces={len(e.face_indices)}")
        raise
    if merged_obj:
        state.merged_layers[layer_name] = merged_obj
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
        config.axis_forward,
        config.axis_up,
        state.unrename_info,
        state.treat_as_static,
        state.temp_scene,
        config.pack_textures_glb,
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
    is_pack_mode = config.pack_textures_glb and config.target_type == "file"
    if is_pack_mode:
        # Pack mode: bake to temp dir, embedded in GLB, cleaned up after
        bake_dir = tempfile.mkdtemp(prefix="nyaa_bake_")
    elif config.target_type == "collection":
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

    # Pack mode: bake on duplicates so originals retain shape keys.
    # bake_prepare is destructive (wipes shape keys, separates/joins by material),
    # but the glTF export needs shape keys. Solution: duplicate meshes, bake on
    # duplicates, assign baked materials back to originals.
    original_mesh_names = list(mesh_names)
    bake_duplicate_names = []
    # Snapshot temp scene contents before bake. Anything new after bake
    # (duplicates, separate/join byproducts) gets cleaned up.
    pre_bake_object_names = (
        {obj.name for obj in state.temp_scene.objects} if is_pack_mode else set()
    )
    if is_pack_mode and mesh_objects:
        duplicates = []
        for orig in mesh_objects:
            dup_data = orig.data.copy()
            dup = orig.copy()
            dup.data = dup_data
            dup.name = orig.name + "__bakedup"
            state.temp_scene.collection.objects.link(dup)
            duplicates.append(dup)
            bake_duplicate_names.append(dup.name)

            # Hide original from rays so it doesn't occlude AO on the duplicate
            orig.hide_render = True

        mesh_objects = duplicates
        mesh_names = bake_duplicate_names
        debug_print(f"Duplicated {len(duplicates)} meshes for bake (originals hidden)")

    # Build mesh metas
    mesh_metas = [
        MeshMeta(mesh_object=obj, layer_name="", is_ue_collider=False)
        for obj in mesh_objects
    ]

    # Convert bake image configs
    if is_pack_mode:
        # Fixed glTF PBR bake set for GLB packing
        bake_configs = [
            BakeImageConfig(format="rgba", image_type="png", width=4096, height=4096, optimize_resolution=True),
            BakeImageConfig(format="ao-ro-me", image_type="png", width=4096, height=4096, optimize_resolution=True),
            BakeImageConfig(format="normalgl", image_type="exr", width=4096, height=4096, optimize_resolution=True),
            BakeImageConfig(format="emission", image_type="png", width=4096, height=4096, optimize_resolution=True),
        ]
    else:
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
    # In pack mode, material assignment targets the ORIGINALS (not duplicates)
    captured_mesh_names = original_mesh_names if is_pack_mode else mesh_names
    captured_pre_bake_names = pre_bake_object_names
    captured_temp_scene = state.temp_scene
    captured_is_pack_mode = is_pack_mode

    def bake_cleanup(reason):
        """Cleanup after bake completes."""
        debug_print(f"[Bake cleanup] reason={reason}")

        # #region HYP-PACK-1: log files in bake dir after bake completes
        import json as _json_p, time as _time_p
        _dbg_p = r"\\wsl.localhost\Ubuntu-24.04\home\nyaarium\.cursor\debug.log"
        _bake_files = []
        if os.path.isdir(tex_dir):
            for fn in os.listdir(tex_dir):
                fp = os.path.join(tex_dir, fn)
                _bake_files.append({
                    "name": fn,
                    "size_bytes": os.path.getsize(fp) if os.path.isfile(fp) else None,
                })
        with open(_dbg_p, "a") as _f:
            _f.write(_json_p.dumps({
                "runId": "pack-texture-001",
                "location": "generator.py:bake_cleanup_start",
                "message": "Files in bake dir after bake",
                "data": {"tex_dir": tex_dir, "files": _bake_files},
                "timestamp": _time_p.time(),
            }) + "\n")
        # #endregion

        # Assign baked materials to originals (pack mode) or merged meshes (normal)
        for mesh_name in captured_mesh_names:
            obj = bpy.data.objects.get(mesh_name)
            if obj and obj.type == "MESH":
                for slot in obj.material_slots:
                    if slot.material:
                        original_mat_name = slot.material.name
                        baked_mat = create_baked_material(slot.material, tex_dir)

                        # #region HYP-PACK-2: log baked material node structure
                        _mat_info = {
                            "mesh": mesh_name,
                            "original_mat_name": original_mat_name,
                            "baked_mat_created": baked_mat is not None,
                        }
                        if baked_mat:
                            _img_nodes = [n for n in baked_mat.node_tree.nodes if n.type == "TEX_IMAGE"]
                            _mat_info["baked_mat_name"] = baked_mat.name
                            _mat_info["image_node_count"] = len(_img_nodes)
                            _mat_info["image_nodes"] = [
                                {
                                    "node_name": n.name,
                                    "image_name": n.image.name if n.image else None,
                                    "image_filepath": n.image.filepath if n.image else None,
                                    "image_size": list(n.image.size) if n.image else None,
                                    "colorspace": n.image.colorspace_settings.name if n.image else None,
                                    "connected_to": [l.to_socket.name for l in n.outputs["Color"].links],
                                }
                                for n in _img_nodes
                            ]
                        with open(_dbg_p, "a") as _f:
                            _f.write(_json_p.dumps({
                                "runId": "pack-texture-001",
                                "location": "generator.py:baked_material_assigned",
                                "message": "Baked material created",
                                "data": _mat_info,
                                "timestamp": _time_p.time(),
                            }) + "\n")
                        # #endregion

                        if baked_mat:
                            slot.material = baked_mat
                            debug_print(f"🎨 Assigned baked material: {baked_mat.name}")

                # Restore render visibility (originals were hidden during bake)
                if captured_is_pack_mode:
                    obj.hide_render = False

        # Snapshot-based cleanup: remove any objects in temp scene that weren't
        # there before bake (duplicates + bake_prepare byproducts)
        if captured_is_pack_mode and captured_temp_scene:
            to_remove = [
                obj for obj in list(captured_temp_scene.objects)
                if obj.name not in captured_pre_bake_names
            ]
            for obj in to_remove:
                obj_data = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if obj_data and obj_data.users == 0:
                    if hasattr(bpy.data, "meshes") and obj_data.__class__.__name__ == "Mesh":
                        bpy.data.meshes.remove(obj_data)
            if to_remove:
                debug_print(f"Removed {len(to_remove)} bake byproduct objects")

        # #region HYP-PACK-3: final state of objects/materials before export
        _final_state = []
        if captured_temp_scene:
            for _o in captured_temp_scene.objects:
                if _o.type == "MESH":
                    _slots = []
                    for _s in _o.material_slots:
                        if _s.material:
                            _img_ns = [n for n in _s.material.node_tree.nodes if n.type == "TEX_IMAGE"]
                            _slots.append({
                                "material": _s.material.name,
                                "image_count": len(_img_ns),
                                "images": [
                                    {"name": n.image.name if n.image else None, "size": list(n.image.size) if n.image else None}
                                    for n in _img_ns
                                ],
                            })
                        else:
                            _slots.append({"material": None})
                    _final_state.append({
                        "mesh": _o.name,
                        "hide_render": _o.hide_render,
                        "slots": _slots,
                    })
        with open(_dbg_p, "a") as _f:
            _f.write(_json_p.dumps({
                "runId": "pack-texture-001",
                "location": "generator.py:bake_cleanup_end",
                "message": "Final mesh/material state after cleanup",
                "data": {"meshes": _final_state},
                "timestamp": _time_p.time(),
            }) + "\n")
        # #endregion

        # Clean up temp bake dir (pack mode only)
        # DEBUG: temporarily don't delete so we can inspect
        if captured_is_pack_mode and os.path.isdir(tex_dir):
            # shutil.rmtree(tex_dir, ignore_errors=True)
            debug_print(f"[DEBUG] Kept temp bake dir for inspection: {tex_dir}")

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

    # Copy world from original scene so AO baking has an environment to trace against
    if state.original_scene.world:
        state.temp_scene.world = state.original_scene.world

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
    print(f"[MergeExport] _cleanup_file_export reason={reason}")
    _cleanup_scene(state)

    if reason == "error":
        _focus_collapsed_uv_faces(state)

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
    print(f"[MergeExport] _cleanup_collection_export reason={reason}")
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

    if reason == "error":
        _focus_collapsed_uv_faces(state)

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


def _focus_collapsed_uv_faces(state: MergeExportState) -> None:
    """
    After renames are restored, enter Edit Mode on the original mesh with
    the collapsed UV faces selected and framed in the viewport.

    Called only when state.collapsed_uv_error is set and reason == "error".
    """
    print("[MergeExport] _focus_collapsed_uv_faces called")

    if not state.collapsed_uv_error:
        print("[MergeExport]   collapsed_uv_error is None — skipping focus")
        return

    original_mesh_name, face_indices = state.collapsed_uv_error
    print(f"[MergeExport]   target object: '{original_mesh_name}', face count: {len(face_indices)}")

    obj = bpy.data.objects.get(original_mesh_name)
    if not obj:
        print(f"[MergeExport]   object '{original_mesh_name}' not found in bpy.data.objects")
        return
    if obj.type != "MESH":
        print(f"[MergeExport]   object '{original_mesh_name}' is type {obj.type}, not MESH")
        return

    print(f"[MergeExport]   object found: {obj.name}, in scene: {obj.name in bpy.context.scene.objects}")

    try:
        # Must set active object BEFORE any mode_set call.
        # Deselect all, then make the target active so mode_set has something to work on.
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        print(f"[MergeExport]   active object set to: {bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else 'None'}")

        # Switch to object mode (required before setting polygon selections)
        bpy.ops.object.mode_set(mode="OBJECT")

        # Reveal hidden geometry and clear selection in edit mode
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.reveal(select=False)
        bpy.ops.mesh.select_all(action="DESELECT")

        # Back to object mode to set polygon selections on the mesh data
        bpy.ops.object.mode_set(mode="OBJECT")

        # Select the collapsed faces on the mesh data (must be in OBJECT mode)
        selected_count = 0
        for face_idx in face_indices:
            if face_idx < len(obj.data.polygons):
                obj.data.polygons[face_idx].select = True
                selected_count += 1
        print(f"[MergeExport]   selected {selected_count} polygons on mesh data")

        # Enter edit mode — the polygon selection transfers automatically
        bpy.ops.object.mode_set(mode="EDIT")
        print("[MergeExport]   entered edit mode")

        # Frame the selection in all 3D viewports
        framed = False
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    region = next(
                        (r for r in area.regions if r.type == "WINDOW"), None
                    )
                    if region:
                        with bpy.context.temp_override(
                            window=window, area=area, region=region
                        ):
                            bpy.ops.view3d.view_selected()
                            framed = True
                            print(f"[MergeExport]   framed selection in viewport")
        if not framed:
            print("[MergeExport]   no 3D viewport found to frame selection")

    except Exception as e:
        import traceback
        print(f"[MergeExport] Error in _focus_collapsed_uv_faces: {e}")
        traceback.print_exc()


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


def _apply_mesh_transforms(temp_scene, debug_print):
    """Bake every object's world transform so the temp scene ends with everything at origin.

    Order matters:
      1. Un-parent each mesh (keep-transform) so the parent armature's contribution
         collapses into the mesh's matrix_basis.
      2. Apply transforms on meshes — vertices end up in world coords.
      3. Apply transforms on armatures — bone rest matrices absorb the armature's world
         transform; armature itself goes to origin.

    Doing the armature first (as the old code did) drops the armature to origin while
    leaving child meshes behind, erasing whatever raise/translation the user did on the
    rig. Doing it last preserves it.

    bpy.ops.object.transform_apply refuses meshes with shape keys, so those are baked
    by transforming the mesh data and each shape key block directly.
    """
    identity = Matrix.Identity(4)

    if bpy.context.active_object:
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")

    # Pass 1: meshes
    for obj in list(temp_scene.objects):
        if obj.type != "MESH":
            continue

        # Un-parent keeping world transform — collapses parent_inverse and basis
        # into a single matrix_basis we can bake.
        if obj.parent is not None:
            mw = obj.matrix_world.copy()
            obj.parent = None
            obj.matrix_parent_inverse = identity
            obj.matrix_basis = mw

        if obj.matrix_basis == identity:
            continue

        mesh = obj.data
        if mesh.shape_keys:
            mat = obj.matrix_basis.copy()
            mesh.transform(mat)
            for kb in mesh.shape_keys.key_blocks:
                for i in range(len(kb.data)):
                    kb.data[i].co = mat @ kb.data[i].co
            obj.matrix_basis = identity
            debug_print(
                f"Applied transform on '{obj.name}' "
                f"(with {len(mesh.shape_keys.key_blocks)} shape keys)"
            )
        else:
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            obj.select_set(False)
            debug_print(f"Applied transform on '{obj.name}'")

    # Pass 2: armatures (after meshes, so the armature's transform has already been
    # captured into the meshes' baked vertex coords).
    for obj in list(temp_scene.objects):
        if obj.type != "ARMATURE":
            continue
        if obj.matrix_local == identity:
            continue

        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        obj.select_set(False)
        debug_print(f"Applied transform on armature '{obj.name}'")


def _finalize_and_export(
    asset_name,
    armature,
    export_path,
    export_format,
    axis_forward,
    axis_up,
    unrename_info,
    is_static_asset,
    temp_scene,
    pack_textures_glb,
    debug_print,
):
    """Finalize merged meshes and export in requested format.

    Axis handling per format:
      FBX  - user's axis_forward/axis_up are written as the file's axis metadata;
             engine importers (Unity, Godot, Unreal) read this and convert.
      glTF - locked to +Y up per spec (export_yup=True).
      OBJ  - locked to -Z forward / +Y up (Blender's wm.obj_export historical default);
             OBJ has no axis metadata, so rotation is baked into vertices.
    """
    if not export_path:
        armature_name = armature.name if armature else asset_name
        raise Exception(f"Export path not found for: {armature_name}")

    # Bake mesh object transforms into vertex coordinates so the exported file carries
    # geometry at its source-file world position. Without this, leftover translations on
    # the merged objects ship as node transforms and engines (or re-importers) drop or
    # reinterpret them differently.
    _apply_mesh_transforms(temp_scene, debug_print)

    # Strip leading "+" for Blender FBX exporter ("Z" not "+Z")
    def _to_fbx_axis(val):
        return val.replace("+", "")

    if export_format == "fbx":
        export_name = asset_name
        path = resolve_path(export_path, export_name + ".fbx")
        os.makedirs(os.path.dirname(path), exist_ok=True)

        fbx_fwd, fbx_up = _to_fbx_axis(axis_forward), _to_fbx_axis(axis_up)
        bpy.ops.export_scene.fbx(
            filepath=path,
            check_existing=False,
            filter_glob="*.fbx",
            use_active_collection=True,
            apply_scale_options="FBX_SCALE_UNITS",
            axis_forward=fbx_fwd,
            axis_up=fbx_up,
            use_mesh_modifiers=False,
            mesh_smooth_type="FACE",
            add_leaf_bones=False,
            bake_anim=False,
        )

    elif export_format == "glb":
        export_name = asset_name

        # Determine GLB vs GLTF_SEPARATE based on the user's path extension
        path_lower = export_path.lower().rstrip("/\\")
        if path_lower.endswith(".gltf"):
            gltf_format = "GLTF_SEPARATE"
            path = resolve_path(export_path, export_name + ".gltf")
        else:
            gltf_format = "GLB"
            path = resolve_path(export_path, export_name + ".glb")

        os.makedirs(os.path.dirname(path), exist_ok=True)

        # #region HYP-ARM-1: state of mesh(es) and armature(s) before export
        import json as _json_a, time as _time_a
        _dbg_a = r"\\wsl.localhost\Ubuntu-24.04\home\nyaarium\.cursor\debug.log"
        _state = []
        for _o in temp_scene.objects:
            _info = {
                "name": _o.name,
                "type": _o.type,
                "parent": _o.parent.name if _o.parent else None,
                "parent_type": _o.parent.type if _o.parent else None,
                "hide_render": _o.hide_render,
                "hide_viewport": _o.hide_viewport,
            }
            if _o.type == "MESH":
                _info["modifiers"] = [
                    {
                        "name": m.name,
                        "type": m.type,
                        "object": m.object.name if hasattr(m, "object") and m.object else None,
                        "show_viewport": m.show_viewport,
                        "show_render": m.show_render,
                    }
                    for m in _o.modifiers
                ]
                _info["vertex_groups"] = [vg.name for vg in _o.vertex_groups]
                _info["vg_count"] = len(_o.vertex_groups)
            elif _o.type == "ARMATURE":
                _info["bone_count"] = len(_o.data.bones)
                _info["bone_names"] = [b.name for b in _o.data.bones][:5]
            _state.append(_info)
        with open(_dbg_a, "a") as _f:
            _f.write(_json_a.dumps({
                "runId": "armature-link-001",
                "location": "generator.py:pre_gltf_export",
                "message": "Mesh/armature state before export",
                "data": {"temp_scene_objects": _state},
                "timestamp": _time_a.time(),
            }) + "\n")
        # #endregion

        # Unless the user opted in to packing baked textures, strip the Surface link
        # on every material so the glTF exporter has no shader graph to traverse.
        # Result: GLB carries geometry + material slots only, with no embedded images
        # and no side-effect unpacking of packed images. User rewires materials in
        # their target engine. Links are restored after export.
        surface_link_snapshots = []
        if not pack_textures_glb:
            seen_mats = set()
            for _obj in temp_scene.objects:
                if _obj.type != "MESH":
                    continue
                for _slot in _obj.material_slots:
                    _mat = _slot.material
                    if _mat is None or _mat.name in seen_mats or not _mat.use_nodes:
                        continue
                    seen_mats.add(_mat.name)
                    _output = None
                    for _node in _mat.node_tree.nodes:
                        if _node.type != "OUTPUT_MATERIAL":
                            continue
                        if getattr(_node, "target", "ALL") == "ALL":
                            _output = _node
                            break
                        if _output is None:
                            _output = _node
                    if _output is None:
                        continue
                    _surface = _output.inputs.get("Surface")
                    if _surface is None or not _surface.is_linked:
                        continue
                    for _link in list(_surface.links):
                        surface_link_snapshots.append(
                            (_mat.node_tree, _link.from_socket, _link.to_socket)
                        )
                        _mat.node_tree.links.remove(_link)

        try:
            bpy.ops.export_scene.gltf(
                filepath=path,
                check_existing=False,
                export_format=gltf_format,
                use_active_scene=True,
                export_hierarchy_full_collections=False,
                export_apply=False,
                export_yup=True,
                export_animations=True,
                export_morph=True,
                export_morph_normal=True,
                export_morph_tangent=False,
            )
        finally:
            for _node_tree, _from_socket, _to_socket in surface_link_snapshots:
                _node_tree.links.new(_from_socket, _to_socket)

        # #region HYP-PACK-4: parse exported GLB and log its image/material/texture structure
        try:
            import json as _json_glb, struct as _struct_glb, time as _time_glb
            _dbg_glb = r"\\wsl.localhost\Ubuntu-24.04\home\nyaarium\.cursor\debug.log"

            with open(path, "rb") as _f_glb:
                _magic = _f_glb.read(4)
                _version = _struct_glb.unpack("<I", _f_glb.read(4))[0]
                _length = _struct_glb.unpack("<I", _f_glb.read(4))[0]
                # JSON chunk
                _json_len = _struct_glb.unpack("<I", _f_glb.read(4))[0]
                _json_type = _f_glb.read(4)
                _json_bytes = _f_glb.read(_json_len)
                _gltf_json = _json_glb.loads(_json_bytes.decode("utf-8"))

            _summary = {
                "magic": _magic.decode("ascii", errors="replace"),
                "version": _version,
                "total_length": _length,
                "json_length": _json_len,
                "scenes": [{"name": s.get("name"), "nodes": s.get("nodes", [])} for s in _gltf_json.get("scenes", [])],
                "nodes_count": len(_gltf_json.get("nodes", [])),
                "nodes": [
                    {
                        "name": n.get("name"),
                        "mesh": n.get("mesh"),
                        "skin": n.get("skin"),
                        "children_count": len(n.get("children", [])),
                        "has_rotation": "rotation" in n,
                        "has_translation": "translation" in n,
                        "has_scale": "scale" in n,
                    }
                    for n in _gltf_json.get("nodes", [])
                ],
                "skins_count": len(_gltf_json.get("skins", [])),
                "skins": [
                    {
                        "name": s.get("name"),
                        "joint_count": len(s.get("joints", [])),
                        "skeleton": s.get("skeleton"),
                    }
                    for s in _gltf_json.get("skins", [])
                ],
                "meshes_count": len(_gltf_json.get("meshes", [])),
                "materials": [
                    {
                        "name": m.get("name"),
                        "pbr_keys": list(m.get("pbrMetallicRoughness", {}).keys()),
                        "has_normal": "normalTexture" in m,
                        "has_occlusion": "occlusionTexture" in m,
                        "has_emissive": "emissiveTexture" in m,
                        "pbr": m.get("pbrMetallicRoughness", {}),
                        "normalTexture": m.get("normalTexture"),
                        "occlusionTexture": m.get("occlusionTexture"),
                        "emissiveTexture": m.get("emissiveTexture"),
                    }
                    for m in _gltf_json.get("materials", [])
                ],
                "textures_count": len(_gltf_json.get("textures", [])),
                "textures": _gltf_json.get("textures", []),
                "images": [
                    {"name": im.get("name"), "mime": im.get("mimeType"), "bufferView": im.get("bufferView"), "uri": im.get("uri")}
                    for im in _gltf_json.get("images", [])
                ],
            }
            with open(_dbg_glb, "a") as _f:
                _f.write(_json_glb.dumps({
                    "runId": "pack-texture-001",
                    "location": "generator.py:post_gltf_export",
                    "message": "GLB file structure after export",
                    "data": _summary,
                    "timestamp": _time_glb.time(),
                }) + "\n")
        except Exception as _e_glb:
            import traceback as _tb_glb
            with open(_dbg_glb, "a") as _f:
                _f.write(_json_glb.dumps({
                    "runId": "pack-texture-001",
                    "location": "generator.py:post_gltf_export",
                    "message": "Failed to parse GLB",
                    "data": {"error": str(_e_glb), "traceback": _tb_glb.format_exc()},
                    "timestamp": _time_glb.time(),
                }) + "\n")
        # #endregion

    elif export_format == "obj":
        export_name = asset_name
        path = resolve_path(export_path, export_name + ".obj")
        os.makedirs(os.path.dirname(path), exist_ok=True)

        bpy.ops.wm.obj_export(
            filepath=path,
            check_existing=False,
            filter_glob="*.obj",
            forward_axis="NEGATIVE_Z",
            up_axis="Y",
        )

    elif export_format == "votv":
        export_votv(asset_name, temp_scene, export_path, unrename_info, debug_print)
