"""
Asset Merge & Export Operator.

Merges mesh layers and exports assets in various formats (FBX, OBJ, VotV).
Supports exporting to files or to a collection as Blender assets.
"""

import os
import traceback
import bpy
from bpy.props import BoolProperty, StringProperty

from ..common.file_stuff import sanitize_name
from ..common.renamer_restore import renamer_restore
from ..common.resolve_path import resolve_path
from ..panels.operators_bake import set_pending_bake_context

from ..asset.asset_lookup import (
    get_asset_by_name,
    get_export_path_from_asset,
)
from ..asset.merge_layers import (
    merge_asset_layers,
    copy_armature_to_collection,
    apply_armature_modifiers_and_remove,
)
from ..asset.export_votv import render_votv_icon, export_votv
from ..asset.export_collection import export_to_collection, create_baked_material


TEMP_SCENE_NAME = "Temp Merge & Export"


class NyaaToolsAssetMergeExport(bpy.types.Operator):
    """Merge and export tool. For Voices of the Void, configure the path to the printer directory."""

    bl_idname = "nyaa.asset_merge_export"
    bl_label = "Merge & Export"
    bl_options = {"REGISTER", "UNDO"}

    asset_name: StringProperty(name="Asset Name", default="")
    export_format: StringProperty(name="Export Format", default="fbx")
    target_type: StringProperty(name="Target Type", default="file")
    export_static: BoolProperty(name="Export Static", default=False)
    bake_after_export: BoolProperty(name="Bake After Export", default=False)
    include_ue_colliders: BoolProperty(name="Include UE Colliders", default=False)

    def execute(self, context):
        try:
            if not self.asset_name:
                self.report({"ERROR"}, "Specify an asset name.")
                return {"CANCELLED"}

            asset_host = get_asset_by_name(self.asset_name)
            if not asset_host:
                self.report({"ERROR"}, f"Asset '{self.asset_name}' not found.")
                return {"CANCELLED"}

            # Validate bake_after_export
            if self.bake_after_export:
                cfg = asset_host.nyaa_asset
                if len(cfg.bake_images) == 0:
                    self.report(
                        {"ERROR"},
                        '"Bake after export" requires bake profiles to be configured.',
                    )
                    return {"CANCELLED"}

            # VotV always includes colliders
            include_colliders = (
                self.include_ue_colliders or self.export_format == "votv"
            )

            # Handle collection export
            if self.target_type == "collection":
                exported, baking_pending = export_to_collection(
                    asset_host,
                    export_static=self.export_static,
                    bake_after_export=self.bake_after_export,
                    include_ue_colliders=include_colliders,
                )
                self.report(
                    {"INFO"},
                    f"Exported to __Export__ collection ({len(exported)} objects)",
                )

                # If baking was requested, invoke modal bake operator
                if baking_pending:
                    bpy.ops.nyaatools.start_bake_queue("INVOKE_DEFAULT")

                return {"FINISHED"}

            # Handle file export
            baking_pending = perform_merge_export(
                asset_host,
                self.export_format,
                export_static=self.export_static,
                bake_after_export=self.bake_after_export,
                include_ue_colliders=include_colliders,
            )

            path = get_export_path_from_asset(asset_host)
            if path:
                path = resolve_path(path, self.asset_name)

            self.report({"INFO"}, "Export successful!  " + (path or ""))

            # If baking was requested, invoke modal bake operator
            if baking_pending:
                bpy.ops.nyaatools.start_bake_queue("INVOKE_DEFAULT")

            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_merge_export(
    asset_host,
    export_format,
    export_static=False,
    bake_after_export=False,
    include_ue_colliders=False,
):
    """
    Merge and export asset using PropertyGroup data.

    Args:
        asset_host: The asset host object (armature or mesh) with nyaa_asset config
        export_format: 'fbx', 'obj', or 'votv'
        export_static: If True, apply pose and modifiers, remove armature
        bake_after_export: If True, bake textures from merged meshes before export
        include_ue_colliders: If True, include UCX_ collision meshes in export
    """

    def debug_print(*msgs):
        print("   ", *msgs)

    # Get asset name
    asset_name = asset_host.nyaa_asset.asset_name

    # Treat as static if mesh-hosted OR export_static is enabled
    is_static_asset = asset_host.type == "MESH"
    treat_as_static = is_static_asset or export_static

    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.outliner.orphans_purge(do_recursive=True)

    # Render VotV icon before modifying scene
    if export_format == "votv":
        render_votv_icon(asset_host, asset_name, debug_print)

    # Create temporary scene
    temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
    if temp_scene:
        bpy.data.scenes.remove(temp_scene, do_unlink=True)
        bpy.ops.outliner.orphans_purge(do_recursive=True)

    temp_scene = bpy.data.scenes.new(name=TEMP_SCENE_NAME)
    original_scene = bpy.context.window.scene
    bpy.context.window.scene = temp_scene

    unrename_info = []
    error = None
    baking_pending = False

    try:
        armature_copy = None

        # For armature-based assets, copy armature to temp scene
        if not is_static_asset:
            armature_copy, arm_unrename = copy_armature_to_collection(
                asset_host, temp_scene.collection, "Armature", debug_print
            )
            unrename_info.extend(arm_unrename)

        # Merge meshes by layer (and optionally process colliders)
        merged_layers, collider_objects, mesh_unrename = merge_asset_layers(
            asset_host,
            temp_scene.collection,
            armature_copy,
            include_colliders=include_ue_colliders,
            debug_print=debug_print,
        )
        unrename_info.extend(mesh_unrename)

        # Apply armature modifier and remove armature if exporting static
        if export_static and armature_copy:
            apply_armature_modifiers_and_remove(
                temp_scene.objects, armature_copy, debug_print
            )
            armature_copy = None

        export_path = get_export_path_from_asset(asset_host)

        # Capture mesh names BEFORE export (VotV export merges meshes, deleting originals)
        # Filter out UCX collision meshes (safety check)
        merged_mesh_list = [
            obj
            for obj in (list(merged_layers.values()) if merged_layers else [])
            if obj.type == "MESH" and not obj.name.upper().startswith("UCX_")
        ]
        mesh_names = [obj.name for obj in merged_mesh_list] if merged_mesh_list else []

        _finalize_and_export(
            asset_name,
            armature_copy,
            export_path,
            export_format,
            unrename_info,
            treat_as_static,
            temp_scene,
            debug_print,
        )

        # Set up pending bake context if baking is requested
        # This must happen AFTER export but BEFORE finally cleanup
        # Note: Only bake non-collider meshes
        if bake_after_export and merged_layers:
            cfg = asset_host.nyaa_asset
            if export_path:
                # For VotV, use the asset export directory (with sanitized asset name)
                if export_format == "votv":
                    clean_asset_name = sanitize_name(asset_name, strict=True)
                    # Check if export path already ends with asset name
                    if export_path.endswith(clean_asset_name):
                        asset_export_dir = export_path
                    else:
                        asset_export_dir = os.path.join(export_path, clean_asset_name)
                    bake_dir = asset_export_dir
                else:
                    bake_dir = os.path.join(
                        os.path.dirname(resolve_path(export_path, "temp")), "textures"
                    )
            else:
                blend_dir = (
                    os.path.dirname(bpy.data.filepath)
                    if bpy.data.filepath
                    else os.getcwd()
                )
                bake_dir = os.path.join(blend_dir, "textures")

            # For VotV exports, meshes are merged into a single object
            # Find the merged object after export (exclude UCX meshes)
            if export_format == "votv":
                clean_asset_name = sanitize_name(asset_name, strict=True)
                merged_obj = None
                for obj in temp_scene.objects:
                    if (
                        obj.type == "MESH"
                        and obj.name == clean_asset_name
                        and not obj.name.upper().startswith("UCX_")
                    ):
                        merged_obj = obj
                        break
                if merged_obj:
                    merged_mesh_list = [merged_obj]
                    mesh_names = [merged_obj.name]
                else:
                    debug_print(
                        f"⚠️ Could not find merged VotV object '{clean_asset_name}'"
                    )
                    merged_mesh_list = []
                    mesh_names = []

            # Capture variables for cleanup lambda
            scene_name = TEMP_SCENE_NAME
            orig_scene = original_scene
            unrename = unrename_info
            tex_dir = bake_dir

            def cleanup_merge_export():
                """Assign baked materials, clean up temp scene, and restore names."""
                # Assign baked materials to merged meshes
                for mesh_name in mesh_names:
                    obj = bpy.data.objects.get(mesh_name)
                    if obj and obj.type == "MESH":
                        for slot in obj.material_slots:
                            if slot.material:
                                baked_mat = create_baked_material(
                                    slot.material, tex_dir
                                )
                                if baked_mat:
                                    slot.material = baked_mat
                                    print(
                                        f"🎨 Assigned baked material: {baked_mat.name}"
                                    )

                # Clean up temp scene
                temp = bpy.data.scenes.get(scene_name)
                if temp:
                    if orig_scene and orig_scene.name in bpy.data.scenes:
                        bpy.context.window.scene = orig_scene
                    bpy.data.scenes.remove(temp, do_unlink=True)
                    bpy.ops.outliner.orphans_purge(do_recursive=True)
                if unrename:
                    renamer_restore(unrename)

            set_pending_bake_context(
                merged_mesh_list,
                cfg.bake_images,
                bake_dir,
                on_cleanup=cleanup_merge_export,
            )
            baking_pending = True
            debug_print(f"🍞 Baking queued for {len(merged_mesh_list)} merged meshes")

    except Exception as e:
        error = e

    finally:
        # Skip cleanup if baking is pending - the cleanup lambda will handle it
        if not baking_pending:
            temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
            if temp_scene:
                bpy.context.window.scene = original_scene
                bpy.data.scenes.remove(temp_scene, do_unlink=True)
                bpy.ops.outliner.orphans_purge(do_recursive=True)
                renamer_restore(unrename_info)

        if error:
            raise error

    return baking_pending


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

        # Ensure parent directory exists
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

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)

        bpy.ops.export_scene.obj(
            filepath=path,
            check_existing=False,
            filter_glob="*.obj",
        )

    elif export_format == "votv":
        export_votv(asset_name, temp_scene, export_path, unrename_info, debug_print)
