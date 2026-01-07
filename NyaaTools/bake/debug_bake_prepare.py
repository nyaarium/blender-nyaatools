"""
Debug operator for testing the bake preparation pipeline.

This operator runs Steps 1-5 of the new baking algorithm and prints
detailed debug info at each stage for human verification.
"""

import bpy
from bpy.types import Operator

from ..bake.bake_context import BakeContext, MeshMeta, BakeImageConfig
from ..bake.bake_prepare import prepare_meshes_for_baking


class NYAATOOLS_OT_DebugBakePrepare(Operator):
    """
    [DEPRECATED] Test the bake preparation pipeline (Steps 1-5) with debug output.
    
    This operator is deprecated. Use Merge & Export with bake_after_export enabled instead.
    """

    bl_idname = "nyaatools.debug_bake_prepare"
    bl_label = "Debug: Bake Prepare (DEPRECATED)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Need an active mesh or armature with nyaa_asset config
        obj = context.active_object
        if not obj:
            return False
        if not hasattr(obj, "nyaa_asset") or not obj.nyaa_asset.is_asset:
            return False
        return True

    def execute(self, context):
        import warnings
        warnings.warn(
            "NYAATOOLS_OT_DebugBakePrepare is deprecated. "
            "Use Merge & Export with bake_after_export enabled instead.",
            DeprecationWarning,
            stacklevel=2
        )
        print("⚠️ DEPRECATED: This operator is deprecated. Use Merge & Export with baking instead.")
        
        asset_host = context.active_object
        cfg = asset_host.nyaa_asset

        print("\n" + "=" * 70)
        print("DEBUG BAKE PREPARE: Starting test run")
        print("=" * 70)
        print(f"Asset: {cfg.asset_name}")
        print(f"Host: {asset_host.name} ({asset_host.type})")
        print()

        # Step 1: Build mesh metas from asset config
        print("-" * 40)
        print("Step 1: Track Asset Metas")
        print("-" * 40)

        mesh_metas = []
        for entry in cfg.meshes:
            if not entry.mesh_object:
                print(f"  ⚠️ Skipping entry with no mesh object")
                continue

            meta = MeshMeta(
                mesh_object=entry.mesh_object,
                layer_name=entry.layer_name,
                is_ue_collider=entry.is_ue_collider,
            )
            mesh_metas.append(meta)

            collider_str = " [COLLIDER]" if entry.is_ue_collider else ""
            print(
                f"  {entry.mesh_object.name} -> layer='{entry.layer_name}'{collider_str}"
            )

        print(f"\nTotal meshes: {len(mesh_metas)}")
        print(
            f"  Non-colliders: {len([m for m in mesh_metas if not m.is_ue_collider])}"
        )
        print(f"  Colliders: {len([m for m in mesh_metas if m.is_ue_collider])}")

        # Create a test bake context (without actually copying to temp scene)
        print("\n" + "=" * 70)
        print("Note: This is a DRY RUN for verification.")
        print("Actual baking requires copying to temp scene first.")
        print("To test the full pipeline, use Merge & Export with bake enabled.")
        print("=" * 70)

        # Show what would happen in each step
        print()
        print("-" * 40)
        print("Step 2: Would delete these colliders:")
        for meta in mesh_metas:
            if meta.is_ue_collider:
                print(f"  DELETE: {meta.mesh_object.name}")

        non_colliders = [m for m in mesh_metas if not m.is_ue_collider]
        print()
        print("-" * 40)
        print("Step 3: Would apply modifiers on these meshes:")
        for meta in non_colliders:
            obj = meta.mesh_object
            print(f"  {obj.name}:")
            if obj.data.shape_keys:
                key_count = len(obj.data.shape_keys.key_blocks)
                print(f"    Shapekeys: {key_count} (would be removed)")
            if obj.modifiers:
                for mod in obj.modifiers:
                    print(f"    Modifier: {mod.name} ({mod.type})")

        print()
        print("-" * 40)
        print("Step 4-5: Would separate and group by material:")

        materials_found = {}
        for meta in non_colliders:
            obj = meta.mesh_object
            if not obj.data.materials:
                mat_name = "__no_material__"
            else:
                for mat in obj.data.materials:
                    mat_name = mat.name if mat else "__no_material__"
                    if mat_name not in materials_found:
                        materials_found[mat_name] = []
                    materials_found[mat_name].append(obj.name)

        for mat_name, mesh_names in materials_found.items():
            print(f"  {mat_name}:")
            for name in mesh_names:
                print(f"    - {name}")

        print("\n" + "=" * 70)
        print("DEBUG BAKE PREPARE: Complete (dry run)")
        print("=" * 70 + "\n")

        self.report({"INFO"}, "Debug output printed to console")
        return {"FINISHED"}


class NYAATOOLS_OT_DebugBakePrepareLive(Operator):
    """
    [DEPRECATED] Actually run bake preparation pipeline (Steps 1-5) with copies in temp scene.
    
    This operator is deprecated. Use Merge & Export with bake_after_export enabled instead.
    """

    bl_idname = "nyaatools.debug_bake_prepare_live"
    bl_label = "Debug: Bake Prepare (LIVE) (DEPRECATED)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj:
            return False
        if not hasattr(obj, "nyaa_asset") or not obj.nyaa_asset.is_asset:
            return False
        return True

    def execute(self, context):
        import warnings
        warnings.warn(
            "NYAATOOLS_OT_DebugBakePrepareLive is deprecated. "
            "Use Merge & Export with bake_after_export enabled instead.",
            DeprecationWarning,
            stacklevel=2
        )
        print("⚠️ DEPRECATED: This operator is deprecated. Use Merge & Export with baking instead.")
        
        asset_host = context.active_object
        cfg = asset_host.nyaa_asset

        print("\n" + "=" * 70)
        print("DEBUG BAKE PREPARE LIVE: Running actual pipeline")
        print("=" * 70)
        print(f"Asset: {cfg.asset_name}")
        print(f"Host: {asset_host.name} ({asset_host.type})")
        print()

        # Create temp scene
        TEMP_SCENE_NAME = "Temp Debug Bake"
        temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
        if temp_scene:
            bpy.data.scenes.remove(temp_scene, do_unlink=True)
            bpy.ops.outliner.orphans_purge(do_recursive=True)

        temp_scene = bpy.data.scenes.new(name=TEMP_SCENE_NAME)
        original_scene = bpy.context.window.scene
        bpy.context.window.scene = temp_scene

        try:
            # Step 1: Copy meshes and build metas
            print("-" * 40)
            print("Step 1: Copying meshes to temp scene")
            print("-" * 40)

            mesh_metas = []
            for entry in cfg.meshes:
                if not entry.mesh_object:
                    continue

                # Copy mesh to temp scene
                mesh_copy = entry.mesh_object.copy()
                mesh_copy.data = entry.mesh_object.data.copy()
                temp_scene.collection.objects.link(mesh_copy)

                meta = MeshMeta(
                    mesh_object=mesh_copy,
                    layer_name=entry.layer_name,
                    is_ue_collider=entry.is_ue_collider,
                    original_name=entry.mesh_object.name,
                )
                mesh_metas.append(meta)

                collider_str = " [COLLIDER]" if entry.is_ue_collider else ""
                print(f"  Copied: {entry.mesh_object.name} -> {mesh_copy.name}{collider_str}")

            if not mesh_metas:
                print("  ⚠️ No meshes to process")
                return {"CANCELLED"}

            # Create context
            ctx = BakeContext(
                mesh_metas=mesh_metas,
                bake_images=[],  # No actual baking in this test
                export_dir="",
                debug_mode=True,
            )

            # Run Steps 2-5
            meshes_by_material = prepare_meshes_for_baking(ctx, debug_print=print)

            # Final summary
            print("\n" + "=" * 70)
            print("FINAL STATE:")
            print("=" * 70)
            print("Objects remaining in temp scene:")
            for obj in temp_scene.objects:
                if obj.type == "MESH":
                    mat_names = [m.name if m else "None" for m in obj.data.materials]
                    print(f"  {obj.name}: materials={mat_names}")

            print("\nMeshes by material:")
            for mat_name, meshes in meshes_by_material.items():
                mesh_names = [m.name for m in meshes]
                print(f"  {mat_name}: {mesh_names}")

            print("\n" + "=" * 70)
            print("DEBUG BAKE PREPARE LIVE: Complete")
            print("=" * 70)
            print("\n⚠️ TEMP SCENE LEFT INTACT FOR INSPECTION")
            print(f"   Scene name: {TEMP_SCENE_NAME}")
            print("   Delete manually when done inspecting.\n")

        except Exception as e:
            import traceback
            print(f"\n❌ ERROR: {e}")
            traceback.print_exc()
            # Clean up on error
            bpy.context.window.scene = original_scene
            temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
            if temp_scene:
                bpy.data.scenes.remove(temp_scene, do_unlink=True)
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        # Note: NOT cleaning up temp scene so user can inspect results
        self.report({"INFO"}, f"Pipeline complete - check console and temp scene: {TEMP_SCENE_NAME}")
        return {"FINISHED"}


class NYAATOOLS_OT_DebugBakeFullPipeline(Operator):
    """
    [DEPRECATED] Run the full bake pipeline including Step 6 (actual baking).
    
    This operator is deprecated. Use Merge & Export with bake_after_export enabled instead.
    """

    bl_idname = "nyaatools.debug_bake_full_pipeline"
    bl_label = "Debug: Full Bake Pipeline (DEPRECATED)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj:
            return False
        if not hasattr(obj, "nyaa_asset") or not obj.nyaa_asset.is_asset:
            return False
        # Must have bake images configured
        if len(obj.nyaa_asset.bake_images) == 0:
            return False
        return True

    def execute(self, context):
        import warnings
        warnings.warn(
            "NYAATOOLS_OT_DebugBakeFullPipeline is deprecated. "
            "Use Merge & Export with bake_after_export enabled instead.",
            DeprecationWarning,
            stacklevel=2
        )
        print("⚠️ DEPRECATED: This operator is deprecated. Use Merge & Export with baking instead.")
        
        import os
        from ..bake.bake_context import BakeContext, MeshMeta, BakeImageConfig
        from ..bake.bake_prepare import prepare_meshes_for_baking
        from ..bake.bake_execute import execute_bake_for_material

        asset_host = context.active_object
        cfg = asset_host.nyaa_asset

        print("\n" + "=" * 70)
        print("DEBUG FULL BAKE PIPELINE: Running complete bake")
        print("=" * 70)
        print(f"Asset: {cfg.asset_name}")
        print(f"Host: {asset_host.name} ({asset_host.type})")
        print(f"Bake images: {len(cfg.bake_images)}")
        print()

        # Create temp scene
        TEMP_SCENE_NAME = "Temp Debug Full Bake"
        temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
        if temp_scene:
            bpy.data.scenes.remove(temp_scene, do_unlink=True)
            bpy.ops.outliner.orphans_purge(do_recursive=True)

        temp_scene = bpy.data.scenes.new(name=TEMP_SCENE_NAME)
        original_scene = bpy.context.window.scene
        bpy.context.window.scene = temp_scene

        # Create output directory
        blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd()
        export_dir = os.path.join(blend_dir, "debug_bake_output")
        os.makedirs(export_dir, exist_ok=True)

        print(f"Export directory: {export_dir}")

        try:
            # Step 1: Copy meshes and build metas
            print("-" * 40)
            print("Step 1: Copying meshes to temp scene")
            print("-" * 40)

            mesh_metas = []
            for entry in cfg.meshes:
                if not entry.mesh_object:
                    continue

                mesh_copy = entry.mesh_object.copy()
                mesh_copy.data = entry.mesh_object.data.copy()
                temp_scene.collection.objects.link(mesh_copy)

                meta = MeshMeta(
                    mesh_object=mesh_copy,
                    layer_name=entry.layer_name,
                    is_ue_collider=entry.is_ue_collider,
                    original_name=entry.mesh_object.name,
                )
                mesh_metas.append(meta)

                collider_str = " [COLLIDER]" if entry.is_ue_collider else ""
                print(f"  Copied: {entry.mesh_object.name} -> {mesh_copy.name}{collider_str}")

            if not mesh_metas:
                print("  ⚠️ No meshes to process")
                return {"CANCELLED"}

            # Convert bake image configs
            bake_configs = []
            for img in cfg.bake_images:
                bake_configs.append(
                    BakeImageConfig(
                        format=img.format,
                        image_type=img.image_type,
                        width=int(img.width),
                        height=int(img.height),
                        optimize_resolution=img.optimize_resolution,
                    )
                )

            # Create context
            ctx = BakeContext(
                mesh_metas=mesh_metas,
                bake_images=bake_configs,
                export_dir=export_dir,
                save_to_file=True,
                wait_for_enter=False,  # Don't wait for user input in debug mode
                debug_mode=True,
            )

            # Run Steps 2-5
            meshes_by_material = prepare_meshes_for_baking(ctx, debug_print=print)

            # Step 6: Execute baking for each material
            print()
            print("=" * 60)
            print("Step 6: Baking textures")
            print("=" * 60)

            for mat_name, meshes in meshes_by_material.items():
                print()
                print(f"Material: {mat_name}")
                try:
                    resolutions = execute_bake_for_material(
                        ctx, mat_name, meshes,
                        debug_print=print,
                        stop_after_node_setup=True  # Stop after node setup for inspection
                    )
                    # When stop_after_node_setup=True, returns empty dict on success
                    # Function always returns a dict
                    print(f"  ✅ Node setup complete for {mat_name}")
                except Exception as e:
                    print(f"  ⚠️ Setup failed for {mat_name}: {e}")

            # Final summary
            print("\n" + "=" * 70)
            print("DEBUG FULL BAKE PIPELINE: Complete")
            print("=" * 70)
            print(f"Output saved to: {export_dir}")
            print(f"Temp scene: {TEMP_SCENE_NAME}")
            print()

        except Exception as e:
            import traceback
            print(f"\n❌ ERROR: {e}")
            traceback.print_exc()
            bpy.context.window.scene = original_scene
            temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
            if temp_scene:
                bpy.data.scenes.remove(temp_scene, do_unlink=True)
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        self.report({"INFO"}, f"Full bake complete - check: {export_dir}")
        return {"FINISHED"}


CLASSES = [
    NYAATOOLS_OT_DebugBakePrepare,
    NYAATOOLS_OT_DebugBakePrepareLive,
    NYAATOOLS_OT_DebugBakeFullPipeline,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
