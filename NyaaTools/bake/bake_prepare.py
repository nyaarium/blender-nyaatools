"""
Bake preparation phase.

Prepares meshes for baking by:
- Deleting collider objects
- Applying modifiers and removing shapekeys
- Separating meshes by material
- Joining compatible meshes to reduce count
"""

from typing import Dict, List, Optional, Callable
import bpy

from .bake_context import BakeContext


def prepare_meshes_for_baking(
    ctx: BakeContext,
    debug_print: Optional[Callable[..., None]] = None,
) -> Dict[str, List[bpy.types.Object]]:
    """
    Prepare meshes for baking.

    This is a destructive operation that modifies the scene objects.
    Only call on copied/temp scene objects.

    Args:
        ctx: The bake context with mesh metadata
        debug_print: Optional debug print function

    Returns:
        Dict mapping material name -> list of mesh objects using that material
    """
    if debug_print is None:

        def debug_print(*args):
            pass

    debug_print("=" * 60)
    debug_print("BAKE PREPARE: Starting mesh preparation")
    debug_print("=" * 60)

    _delete_colliders(ctx, debug_print)
    _apply_modifiers_and_wipe_shapekeys(ctx, debug_print)
    meshes_by_material = _separate_by_material(ctx, debug_print)
    meshes_by_material = _join_meshes_by_material(meshes_by_material, debug_print)

    # Store in context
    ctx.meshes_by_material = meshes_by_material

    debug_print("=" * 60)
    debug_print("BAKE PREPARE: Complete")
    debug_print(f"  Materials: {list(meshes_by_material.keys())}")
    for mat_name, meshes in meshes_by_material.items():
        debug_print(f"    {mat_name}: {len(meshes)} mesh(es)")
    debug_print("=" * 60)

    return meshes_by_material


def _delete_colliders(
    ctx: BakeContext,
    debug_print: Callable[..., None],
) -> None:
    """
    Delete collider objects.

    Uses is_ue_collider flag from MeshMeta, not UCX_ name checking.
    """
    debug_print("-" * 40)
    debug_print("Delete collider objects")

    colliders = ctx.get_collider_meshes()
    if not colliders:
        debug_print("  No colliders to delete")
        return

    for obj in colliders:
        debug_print(f"  Deleting collider: {obj.name}")
        bpy.data.objects.remove(obj, do_unlink=True)

    # Remove deleted meshes from context
    ctx.mesh_metas = [m for m in ctx.mesh_metas if not m.is_ue_collider]

    debug_print(f"  Deleted {len(colliders)} collider(s)")


def _apply_modifiers_and_wipe_shapekeys(
    ctx: BakeContext,
    debug_print: Callable[..., None],
) -> None:
    """
    Apply all modifiers and remove all shapekeys.

    This flattens the mesh for reliable baking.
    """
    debug_print("-" * 40)
    debug_print("Apply modifiers & wipe shapekeys")

    meshes = ctx.get_non_collider_meshes()

    for obj in meshes:
        if obj.type != "MESH":
            continue

        debug_print(f"  Processing: {obj.name}")

        # Ensure we're in OBJECT mode
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        # Select and activate
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # Remove all shapekeys using direct method (doesn't require context)
        if obj.data.shape_keys:
            shape_count = len(obj.data.shape_keys.key_blocks)
            debug_print(f"    Removing {shape_count} shapekeys")
            try:
                # Remove all shapekeys by iterating and removing each one
                # Remove in reverse order to avoid index shifting issues
                key_blocks = list(obj.data.shape_keys.key_blocks)
                for key_block in reversed(key_blocks):
                    obj.shape_key_remove(key_block)
            except Exception as e:
                raise RuntimeError(f"Failed to remove shapekeys from '{obj.name}': {e}")

        # Apply all modifiers
        modifier_names = [m.name for m in obj.modifiers]
        for mod_name in modifier_names:
            mod = obj.modifiers.get(mod_name)
            if not mod:
                continue

            # Delete helpers (name starts with "--")
            if mod.name.startswith("--"):
                debug_print(f"    Deleting helper modifier: {mod_name}")
                obj.modifiers.remove(mod)
                continue

            # Delete Armatures (safe to delete for baking)
            if mod.type == "ARMATURE":
                debug_print(f"    Deleting armature modifier: {mod_name}")
                obj.modifiers.remove(mod)
                continue

            # Enable hidden modifiers so they can be applied
            if not mod.show_viewport:
                debug_print(f"    Enabling hidden modifier for bake: {mod_name}")
                mod.show_viewport = True

            # Apply
            try:
                with bpy.context.temp_override(object=obj):
                    bpy.ops.object.modifier_apply(modifier=mod_name)
                debug_print(f"    Applied modifier: {mod_name}")
            except Exception as e:
                raise RuntimeError(
                    f"Failed to apply modifier '{mod_name}' on '{obj.name}': {e}"
                )


def _separate_by_material(
    ctx: BakeContext,
    debug_print: Callable[..., None],
) -> Dict[str, List[bpy.types.Object]]:
    """
    Separate all meshes by material.

    After this, each mesh object has exactly one material.
    Returns a dict mapping material name -> list of mesh objects.
    """
    debug_print("-" * 40)
    debug_print("Separate by material")

    meshes_by_material: Dict[str, List[bpy.types.Object]] = {}
    meshes_to_process = ctx.get_non_collider_meshes().copy()

    for obj in meshes_to_process:
        if obj.type != "MESH":
            continue

        material_count = len(obj.material_slots)
        debug_print(f"  Processing: {obj.name} ({material_count} materials)")

        if material_count <= 1:
            # Single material or no materials - just track it
            mat_name = _get_material_name(obj)
            if mat_name not in meshes_by_material:
                meshes_by_material[mat_name] = []
            meshes_by_material[mat_name].append(obj)
            debug_print(f"    Single material: {mat_name}")
            continue

        # Multiple materials - separate
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # Store original name for tracking
        original_name = obj.name

        try:
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.separate(type="MATERIAL")
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception as e:
            debug_print(f"    ⚠️ Could not separate by material: {e}")
            bpy.ops.object.mode_set(mode="OBJECT")
            # Still track what we have
            mat_name = _get_material_name(obj)
            if mat_name not in meshes_by_material:
                meshes_by_material[mat_name] = []
            meshes_by_material[mat_name].append(obj)
            continue

        # Find all resulting pieces (selected after separate)
        for piece in bpy.context.selected_objects:
            if piece.type != "MESH":
                continue

            mat_name = _get_material_name(piece)
            if mat_name not in meshes_by_material:
                meshes_by_material[mat_name] = []
            meshes_by_material[mat_name].append(piece)
            debug_print(f"    Separated piece: {piece.name} -> {mat_name}")

    # Update context mesh_metas to reflect new objects
    _update_mesh_metas_after_separate(ctx, meshes_by_material, debug_print)

    debug_print(f"  Total materials found: {len(meshes_by_material)}")
    return meshes_by_material


def _join_meshes_by_material(
    meshes_by_material: Dict[str, List[bpy.types.Object]],
    debug_print: Callable[..., None],
) -> Dict[str, List[bpy.types.Object]]:
    """
    Join meshes that share the same material and compatible UV maps.

    Only joins meshes if their first UV Map name matches.
    Before joining:
    - Checks if any mesh has a UVMap that's NOT in the first slot (error if found)
    - Renames all first UV layers to "UVMap" for consistency
    If names differ, they likely have conflicting UV setups and must remain
    separate to be handled by the multi-mesh bake flow.
    """
    debug_print("-" * 40)
    debug_print("Join meshes by material (matching UV names)")

    result: Dict[str, List[bpy.types.Object]] = {}

    for mat_name, meshes in meshes_by_material.items():
        if len(meshes) == 0:
            continue

        if len(meshes) == 1:
            result[mat_name] = meshes
            debug_print(f"  {mat_name}: 1 mesh (no join needed)")
            continue

        # Group by 1st UV name
        uv_groups: Dict[str, List[bpy.types.Object]] = {}
        for mesh in meshes:
            uv_name = ""
            if mesh.data.uv_layers:
                uv_name = mesh.data.uv_layers[0].name

            if uv_name not in uv_groups:
                uv_groups[uv_name] = []
            uv_groups[uv_name].append(mesh)

        # Join each group
        joined_meshes_for_mat = []

        for uv_name, group_meshes in uv_groups.items():
            if len(group_meshes) == 1:
                joined_meshes_for_mat.append(group_meshes[0])
                debug_print(f"  {mat_name} [UV: '{uv_name}']: 1 mesh (kept separate)")
                continue

            debug_print(
                f"  {mat_name} [UV: '{uv_name}']: Joining {len(group_meshes)} meshes"
            )

            # Check for UVMap conflicts and rename first UV to UVMap
            try:
                for mesh in group_meshes:
                    if not mesh.data.uv_layers:
                        continue

                    # Check if UVMap exists in a non-first slot
                    uvmap_found = False
                    uvmap_slot = -1
                    for idx, uv_layer in enumerate(mesh.data.uv_layers):
                        if uv_layer.name == "UVMap":
                            uvmap_found = True
                            uvmap_slot = idx
                            break

                    if uvmap_found and uvmap_slot != 0:
                        raise RuntimeError(
                            f"Mesh '{mesh.name}' has a UVMap in slot {uvmap_slot + 1}, but it must be in slot 1. "
                            f"Please rename or reorder UV layers so the first UV layer is named 'UVMap'."
                        )

                    # Rename first UV to UVMap if it's not already
                    first_uv = mesh.data.uv_layers[0]
                    if first_uv.name != "UVMap":
                        debug_print(
                            f"    Renaming first UV '{first_uv.name}' to 'UVMap' on {mesh.name}"
                        )
                        first_uv.name = "UVMap"

                # Now join the meshes
                bpy.ops.object.select_all(action="DESELECT")
                for m in group_meshes:
                    if m.name in bpy.data.objects:
                        m.select_set(True)

                bpy.context.view_layer.objects.active = group_meshes[0]
                bpy.ops.object.join()

                joined = bpy.context.view_layer.objects.active
                joined_meshes_for_mat.append(joined)
                debug_print(f"    Joined into: {joined.name}")
            except RuntimeError as e:
                # Re-raise our custom errors
                raise
            except Exception as e:
                debug_print(f"    ⚠️ Join failed: {e}")
                joined_meshes_for_mat.extend(group_meshes)

        result[mat_name] = joined_meshes_for_mat

    return result


def _get_material_name(obj: bpy.types.Object) -> str:
    """Get the material name for a mesh object."""
    if not obj.material_slots or not obj.material_slots[0].material:
        return "__no_material__"
    return obj.material_slots[0].material.name


def _update_mesh_metas_after_separate(
    ctx: BakeContext,
    meshes_by_material: Dict[str, List[bpy.types.Object]],
    debug_print: Callable[..., None],
) -> None:
    """Update mesh metas after separation to track new objects."""
    # Clear old metas (originals are now split)
    ctx.mesh_metas.clear()

    # Create new metas for each separated piece
    # Note: None of these are colliders (colliders were deleted in step 2)
    from .bake_context import MeshMeta

    for mat_name, meshes in meshes_by_material.items():
        for mesh in meshes:
            meta = MeshMeta(
                mesh_object=mesh,
                layer_name="",
                is_ue_collider=False,
            )
            ctx.mesh_metas.append(meta)
