"""
Bake generator for chainable operations.

This module provides a reusable generator function that can be used by
the standalone bake operator or chained from merge-export/batch operators.
"""

import bpy
import os
import traceback

from dataclasses import dataclass
from typing import Callable, Dict, Generator, List, Optional, Tuple

from ...image.texture_baker import (
    _parse_format_string,
    _get_bake_type_for_channels,
    DTP_SOCKET_MAP,
)
from ...image.material_analyzer import find_principled_bsdf, detect_best_resolution
from ...bake.bake_context import BakeContext, BakeImageConfig
from ...bake.bake_prepare import prepare_meshes_for_baking
from ...bake.bake_execute import execute_bake_for_material
from ...ui.task_system import Task, TaskStatus, DrawHelper, LINE_HEIGHT, FONT_SIZE_BODY
from ...ui.ProgressManager import AddTask


# =============================================================================
# State
# =============================================================================


@dataclass
class BakeState:
    """Mutable state container for bake operations."""

    baked_count: int = 0
    failed_count: int = 0


# =============================================================================
# Custom Row Renderer
# =============================================================================


# Column widths for bake task rendering
BAKE_COL_WIDTH_STATUS = 100  # Status column
BAKE_COL_WIDTH_TIME = 80  # Time column
BAKE_COL_WIDTH_MATERIAL = 250  # Material name column
BAKE_COL_WIDTH_FORMAT = 100  # DTP format column
BAKE_COL_WIDTH_TYPE = 80  # Image type column (PNG, EXR)
BAKE_COL_WIDTH_RESOLUTION = 100  # Resolution column


def render_bake_row(task: Task, x: int, y: int, draw: DrawHelper) -> int:
    """
    Custom render for bake task rows.

    Format: [Status] [Time] [Material] [Format] [Type] [Resolution]
    """
    params = task.params
    col_x = x

    # Status column (fixed width)
    status_color = draw.get_status_color(task.status)
    status_text = draw.get_status_text(task.status)
    draw.draw_text(status_text, col_x, y, FONT_SIZE_BODY, status_color)
    col_x += BAKE_COL_WIDTH_STATUS

    # Time column (fixed width, only show if done or failed)
    if task.status in (TaskStatus.DONE, TaskStatus.FAILED) and task.elapsed_seconds > 0:
        time_text = draw.format_seconds(task.elapsed_seconds)
        draw.draw_text(time_text, col_x, y, FONT_SIZE_BODY, status_color)
    col_x += BAKE_COL_WIDTH_TIME

    # Material name column (fixed width)
    mat_name = params.get("material_name", "")
    draw.draw_text(mat_name, col_x, y, FONT_SIZE_BODY, draw.COLOR_TEXT)
    col_x += BAKE_COL_WIDTH_MATERIAL

    # DTP format column (fixed width, grey)
    dtp_format = params.get("dtp_format", "")
    draw.draw_text(dtp_format, col_x, y, FONT_SIZE_BODY, draw.COLOR_TEXT_DIM)
    col_x += BAKE_COL_WIDTH_FORMAT

    # Image type column (fixed width)
    img_type = params.get("img_type", "").upper()
    draw.draw_text(img_type, col_x, y, FONT_SIZE_BODY, draw.COLOR_TEXT_DIM)
    col_x += BAKE_COL_WIDTH_TYPE

    # Resolution column (fixed width)
    if task.status == TaskStatus.DONE and task.result:
        res_text = task.result.get("result_resolution", params.get("resolution", ""))
    else:
        res_text = params.get("resolution", "")
    draw.draw_text(res_text, col_x, y, FONT_SIZE_BODY, draw.COLOR_TEXT_DIM)

    return LINE_HEIGHT


# =============================================================================
# Resolution Detection
# =============================================================================


def _detect_render_resolution(
    material: bpy.types.Material,
    dtp_format: str,
    max_resolution: Tuple[int, int],
) -> Tuple[int, int]:
    """Detect render resolution for a material based on its shader graph."""

    if not material or not material.use_nodes:
        return max_resolution

    principled_result = find_principled_bsdf(material)
    if not principled_result:
        return max_resolution

    principled_bsdf = principled_result["principled_bsdf"]
    tree_stack = principled_result["tree_stack"]

    try:
        channels = _parse_format_string(dtp_format)
        bake_type = _get_bake_type_for_channels(channels)
    except (ValueError, AttributeError):
        return max_resolution

    detected_resolution = None

    if bake_type == "NORMAL":
        normal_socket = principled_bsdf.inputs.get("Normal")
        if normal_socket and normal_socket.is_linked:
            detected_resolution = detect_best_resolution(normal_socket, tree_stack)
        else:
            detected_resolution = (1024, 1024)
    else:
        resolutions = []

        base_color_socket = principled_bsdf.inputs.get("Base Color")
        if base_color_socket and base_color_socket.is_linked:
            resolutions.append(detect_best_resolution(base_color_socket, tree_stack))

        emission_color_socket = principled_bsdf.inputs.get("Emission Color")
        if emission_color_socket and emission_color_socket.is_linked:
            resolutions.append(
                detect_best_resolution(emission_color_socket, tree_stack)
            )

        for channel in channels:
            socket_mapping = DTP_SOCKET_MAP.get(channel)
            if isinstance(socket_mapping, str) and socket_mapping not in (
                "__CONSTANT_0__",
                "__CONSTANT_1__",
                "__UNUSED__",
            ):
                socket = principled_bsdf.inputs.get(socket_mapping)
                if socket and socket.is_linked:
                    resolutions.append(detect_best_resolution(socket, tree_stack))
            elif isinstance(socket_mapping, tuple):
                socket_name, _ = socket_mapping
                socket = principled_bsdf.inputs.get(socket_name)
                if socket and socket.is_linked:
                    resolutions.append(detect_best_resolution(socket, tree_stack))

        if resolutions:
            detected_resolution = (
                max(r[0] for r in resolutions),
                max(r[1] for r in resolutions),
            )
        else:
            detected_resolution = (512, 512)

    if detected_resolution:
        max_width, max_height = max_resolution
        return (
            min(detected_resolution[0], max_width),
            min(detected_resolution[1], max_height),
        )

    return max_resolution


# =============================================================================
# Generator
# =============================================================================


def create_bake_generator(
    bake_ctx: BakeContext,
    state: BakeState,
    debug_print: Optional[Callable] = None,
) -> Generator:
    """
    Create a generator that yields bake tasks.

    Args:
        bake_ctx: The bake context with meshes and configs
        state: Mutable state to track baked/failed counts
        debug_print: Optional debug print function

    Yields:
        AddTask commands for each bake operation
    """
    if debug_print is None:

        def debug_print(*args):
            print("   ", *args)

    # Run prepare phase
    debug_print("[Bake] Preparing meshes for baking...")
    meshes_by_material = prepare_meshes_for_baking(bake_ctx, debug_print=debug_print)

    if not meshes_by_material:
        debug_print("[Bake] No materials found after preparation")
        return

    os.makedirs(bake_ctx.export_dir, exist_ok=True)
    debug_print(f"[Bake] Export directory: {bake_ctx.export_dir}")
    debug_print(f"[Bake] Materials to bake: {list(meshes_by_material.keys())}")

    for mat_name, meshes in meshes_by_material.items():
        material = bpy.data.materials.get(mat_name)
        if not material:
            debug_print(f"[Bake] Material '{mat_name}' not found, skipping")
            continue

        for bake_img in bake_ctx.bake_images:
            dtp_format = bake_img.format
            width = bake_img.width
            height = bake_img.height
            img_type = bake_img.image_type
            optimize = bake_img.optimize_resolution
            res_str = f"{width}x{height}"

            # Detect render resolution if optimize is enabled
            render_width, render_height = width, height
            if optimize and material:
                try:
                    detected = _detect_render_resolution(
                        material, dtp_format, (width, height)
                    )
                    render_width, render_height = detected
                except Exception as e:
                    debug_print(
                        f"[Bake] Resolution detection failed for {mat_name}: {e}"
                    )

            render_res_str = f"{render_width}x{render_height}"

            # Capture for closure
            mn = mat_name
            ms = meshes
            df = dtp_format
            ctx = bake_ctx
            st = state

            def do_bake(context, mn=mn, ms=ms, df=df, ctx=ctx, st=st):
                return _execute_bake_task(ctx, st, mn, ms, df, debug_print)

            yield AddTask(
                Task(
                    id=f"bake_{mat_name}_{dtp_format}",
                    label=f"Bake: {mat_name} / {dtp_format}",
                    execute=do_bake,
                    render_row=render_bake_row,
                    params={
                        "material_name": mat_name,
                        "dtp_format": dtp_format,
                        "img_type": img_type,
                        "resolution": res_str,
                        "render_resolution": render_res_str,
                    },
                )
            )


def _execute_bake_task(
    bake_ctx: BakeContext,
    state: BakeState,
    mat_name: str,
    meshes: List,
    dtp_format: str,
    debug_print: Callable,
) -> Dict:
    """Execute a single bake task."""
    try:
        resolutions = execute_bake_for_material(
            bake_ctx,
            mat_name,
            meshes,
            debug_print=debug_print,
        )

        if resolutions and dtp_format in resolutions:
            width, height = resolutions[dtp_format]
            state.baked_count += 1
            return {
                "success": True,
                "resolution": (width, height),
                "result_resolution": f"{width}x{height}",
            }
        else:
            state.failed_count += 1
            return {
                "success": False,
                "resolution": None,
                "result_resolution": "",
            }

    except Exception as e:
        print(f"[BakeTask] ERROR baking {mat_name} / {dtp_format}: {e}")

        traceback.print_exc()
        state.failed_count += 1
        return {
            "success": False,
            "resolution": None,
            "result_resolution": "",
            "error": str(e),
        }
