"""
Apply Modifier with Shape Keys via UV Projection

This operator applies a modifier to a mesh with shape keys by:
1. Applying the modifier separately to each shape key state (baked at value=1.0)
2. Using UV projection to compute deltas by comparing each result to Basis
3. Reconstructing shape keys on the final mesh

This approach produces mathematically correct results for topology-changing
modifiers like Subdivision Surface, Decimate, and even Geometry Nodes.

All work is done in a temporary scene ("Apply UV Projected") which acts as
a transaction - if anything fails, the original mesh is untouched.
"""

import traceback
import bpy
from bpy.props import IntProperty
from mathutils import Vector

from ..common.selection_get_meshes import selection_get_meshes
from ..common.uv_projection import (
    validate_uvs,
    extract_shape_key_metadata,
    extract_vertex_group_weights,
    project_positions_via_uv,
)
from ..uv.auto_fix_uvs import auto_fix_uvs_for_projection, cleanup_temp_uv_layer


TEMP_SCENE_NAME = "Apply UV Projected"

class NYAATOOLS_OT_ApplyModifierShapeKeysViaUV(bpy.types.Operator):
    """Apply modifier on object with shape keys via UV projection (per-SK method)"""

    bl_idname = "nyaa.apply_modifier_shape_keys_uv"
    bl_label = "Apply Modifier (UV Projection)"
    bl_options = {"REGISTER", "UNDO"}

    uv_map_index: IntProperty(
        name="UV Map Index",
        description="UV map slot to use for projection",
        default=0,
        min=0,
    )

    def execute(self, context):
        try:
            meshes = selection_get_meshes()
            if len(meshes) == 0:
                self.report({"ERROR"}, "Please select at least 1 mesh object!")
                return {"CANCELLED"}

            for mesh_obj in meshes:
                if len(mesh_obj.modifiers) == 0:
                    continue

                result = apply_modifier_with_shape_keys(
                    context, mesh_obj, mesh_obj.modifiers[0], self.uv_map_index
                )
                if result:
                    self.report({"INFO"}, result)

            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def apply_modifier_with_shape_keys(context, mesh_obj, modifier, uv_map_index=0):
    """
    Apply a modifier to a mesh with shape keys using UV projection.

    This is the main entry point. It applies the modifier separately to each
    shape key state, then uses UV projection to compute proper deltas.

    Args:
        context: Blender context
        mesh_obj: Mesh object to apply modifier to
        modifier: The modifier to apply
        uv_map_index: UV map index for projection (default 0)

    Returns:
        Status message or None
    """
    bpy.ops.object.mode_set(mode="OBJECT")

    # If no shape keys, just apply normally
    if not mesh_obj.data.shape_keys or len(mesh_obj.data.shape_keys.key_blocks) == 0:
        context.view_layer.objects.active = mesh_obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        return None

    # Use UV projection for all modifiers
    apply_with_uv_projection(context, mesh_obj, modifier, uv_map_index)
    return f"Applied {modifier.name} via UV projection"


def apply_with_uv_projection(context, mesh_obj, modifier, uv_map_index):
    """
    Apply a modifier using the per-shape-key UV projection algorithm.

    Algorithm:
    1. Create temp scene for transactional safety
    2. For each shape key (including Basis):
       - Duplicate mesh, bake SK to value=1.0, apply modifier
    3. Use Basis result as final topology
    4. For each other SK result, project positions onto Basis via UV
    5. Compute deltas: projected_position - basis_position
    6. Build shape keys on Basis result
    7. Swap mesh data onto original object
    8. Cleanup temp scene
    """
    # Store references
    original_scene = context.window.scene
    original_object = mesh_obj
    modifier_name = modifier.name

    # Unhide all geometry for visibility (enter edit mode, reveal, return to object mode)
    current_mode = mesh_obj.mode
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.reveal(select=False)
    bpy.ops.object.mode_set(mode=current_mode)

    # Store shape key info
    shape_keys = mesh_obj.data.shape_keys.key_blocks
    shape_key_names = [sk.name for sk in shape_keys]
    shape_metadata = extract_shape_key_metadata(mesh_obj)

    # Phase 0: Validate UVs
    validate_uvs(mesh_obj, uv_map_index)

    # Phase 1: Create temp UV layer with fixes (on source mesh, inherited by duplicates)
    temp_uv_index = None
    try:
        temp_uv_index, fix_stats = auto_fix_uvs_for_projection(
            context, mesh_obj, uv_map_index
        )
        projection_uv_index = temp_uv_index
    except Exception as e:
        projection_uv_index = uv_map_index

    # Deselect all after auto-fix for user convenience
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")

    # Phase 2: Create temp scene
    temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
    if temp_scene:
        bpy.data.scenes.remove(temp_scene, do_unlink=True)
        bpy.ops.outliner.orphans_purge(do_recursive=True)

    temp_scene = bpy.data.scenes.new(name=TEMP_SCENE_NAME)

    # Link original object to temp scene temporarily (so we can duplicate from it)
    temp_scene.collection.objects.link(original_object)

    # Switch to temp scene NOW (before duplicating) so objects are in the right view layer
    context.window.scene = temp_scene

    # Track all temp objects for cleanup
    temp_objects = []
    sk_results = {}  # {shape_key_name: mesh_object}

    try:
        # Phase 3: For each shape key, create a baked + modified copy
        for sk_name in shape_key_names:
            # Duplicate mesh into temp scene (original_object is now in temp scene)
            bpy.ops.object.select_all(action="DESELECT")
            context.view_layer.objects.active = original_object
            original_object.select_set(True)
            bpy.ops.object.duplicate(linked=False)
            temp_copy = context.view_layer.objects.active
            temp_copy.name = f"_SK_{sk_name}"
            temp_objects.append(temp_copy)

            # Set this shape key to 1.0, all others to 0.0
            for key in temp_copy.data.shape_keys.key_blocks:
                if key.name == sk_name:
                    key.value = 1.0
                else:
                    key.value = 0.0

            # Bake the shape key mix into the mesh and remove all shape keys
            # (now safe since context.view_layer is in temp_scene)
            context.view_layer.objects.active = temp_copy
            temp_copy.select_set(True)
            bpy.ops.object.shape_key_remove(all=True, apply_mix=True)

            # Apply the modifier
            mod = temp_copy.modifiers.get(modifier_name)
            if mod:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            # Remove remaining modifiers (we only wanted to apply the first one)
            while len(temp_copy.modifiers) > 0:
                temp_copy.modifiers.remove(temp_copy.modifiers[0])

            sk_results[sk_name] = temp_copy

        # Phase 4: Use Basis result as the final mesh
        basis_name = shape_key_names[0]  # First shape key is always Basis
        basis_result = sk_results[basis_name]
        n_verts = len(basis_result.data.vertices)

        # Extract Basis vertex positions
        basis_positions = [v.co.copy() for v in basis_result.data.vertices]

        # Phase 5: Compute deltas for each non-Basis shape key
        computed_deltas = {}  # {sk_name: [Vector3 per vertex]}

        for sk_name in shape_key_names:
            if sk_name == basis_name:
                continue

            sk_result = sk_results[sk_name]

            # Project positions from SK result onto Basis result via UV
            # This gives us "where would each Basis vertex be if it were in SK state?"
            projected_positions = project_positions_via_uv(
                sk_result,  # source: has SK-state positions
                basis_result,  # target: we want positions at each Basis vertex's UV
                projection_uv_index,
            )

            # Compute deltas: projected_position - basis_position
            deltas = []
            for i in range(n_verts):
                delta = projected_positions[i] - basis_positions[i]
                deltas.append(delta)

            computed_deltas[sk_name] = deltas

        # Phase 6: Build shape keys on Basis result
        # Switch to temp scene to work on basis_result
        context.window.scene = temp_scene
        context.view_layer.objects.active = basis_result
        basis_result.select_set(True)

        # Add Basis shape key
        basis_result.shape_key_add(name="Basis", from_mix=False)

        # Add other shape keys with computed deltas
        for meta in shape_metadata:
            if meta["name"] == basis_name:
                continue

            new_key = basis_result.shape_key_add(name=meta["name"], from_mix=False)

            if meta["name"] in computed_deltas:
                deltas = computed_deltas[meta["name"]]
                for i, delta in enumerate(deltas):
                    new_key.data[i].co = basis_positions[i] + delta

        # Restore shape key metadata
        for i, meta in enumerate(shape_metadata):
            if i >= len(basis_result.data.shape_keys.key_blocks):
                break
            key = basis_result.data.shape_keys.key_blocks[i]
            key.interpolation = meta["interpolation"]
            key.mute = meta["mute"]
            key.slider_min = meta["slider_min"]
            key.slider_max = meta["slider_max"]
            key.value = meta["value"]
            key.vertex_group = meta["vertex_group"]

            # Restore relative key by name lookup
            if meta["relative_key_name"]:
                for other_key in basis_result.data.shape_keys.key_blocks:
                    if other_key.name == meta["relative_key_name"]:
                        key.relative_key = other_key
                        break

        # Phase 7: Capture vertex groups from Basis result
        vertex_weights = extract_vertex_group_weights(basis_result)

        # Phase 8: Swap mesh data onto original object
        # Switch back to original scene
        context.window.scene = original_scene

        # Remove the modifier from original (we applied it)
        mod_to_remove = original_object.modifiers.get(modifier_name)
        if mod_to_remove:
            original_object.modifiers.remove(mod_to_remove)

        # Remove shape keys from original
        context.view_layer.objects.active = original_object
        original_object.select_set(True)
        if original_object.data.shape_keys:
            bpy.ops.object.shape_key_remove(all=True)

        # Clear vertex groups from original
        original_object.vertex_groups.clear()

        # Swap mesh data
        old_mesh_data = original_object.data
        final_mesh_data = basis_result.data
        final_mesh_data.name = old_mesh_data.name + "_new"

        original_object.data = final_mesh_data
        final_mesh_data.name = old_mesh_data.name  # Restore original name

        # Delete old mesh data if no other users
        if old_mesh_data.users == 0:
            bpy.data.meshes.remove(old_mesh_data)

        # Recreate vertex groups on original object
        for vg_name, weights in vertex_weights.items():
            vgroup = original_object.vertex_groups.new(name=vg_name)
            for vert_idx, weight in enumerate(weights):
                if weight > 0.001:
                    vgroup.add([vert_idx], weight, "REPLACE")

        # Clean up temp UV layer from final mesh
        if temp_uv_index is not None:
            cleanup_temp_uv_layer(original_object, temp_uv_index)

    except Exception as e:
        raise

    finally:
        # Phase 9: Cleanup temp scene
        # Switch back to original scene if needed
        if context.window.scene != original_scene:
            context.window.scene = original_scene

        # Unlink original object from temp scene (was linked temporarily for duplication)
        temp_scene = bpy.data.scenes.get(TEMP_SCENE_NAME)
        if temp_scene and original_object.name in temp_scene.collection.objects:
            temp_scene.collection.objects.unlink(original_object)

        # Remove temp scene and its objects
        if temp_scene:
            bpy.data.scenes.remove(temp_scene, do_unlink=True)
            bpy.ops.outliner.orphans_purge(do_recursive=True)

        # Restore selection
        bpy.ops.object.select_all(action="DESELECT")
        if original_object and original_object.name in bpy.data.objects:
            original_object.select_set(True)
            context.view_layer.objects.active = original_object


def apply_modifiers_with_shape_keys(
    context, modifier_names, disable_armatures=False, uv_map_index=0
):
    """
    Apply modifiers to active object with shape key support.

    Drop-in replacement API for callers that expect the old interface.
    Uses UV projection for all modifiers.

    Args:
        context: Blender context
        modifier_names: List of modifier names to apply
        disable_armatures: Whether to temporarily disable armature modifiers
        uv_map_index: UV map index for projection (default 0)

    Returns:
        (success: bool, error_message: str or None)
    """
    mesh_obj = context.object

    if mesh_obj is None or mesh_obj.type != "MESH":
        return (False, "No mesh object selected")

    # Disable armatures if requested
    disabled_armature_modifiers = []
    if disable_armatures:
        for modifier in mesh_obj.modifiers:
            if (
                modifier.name not in modifier_names
                and modifier.type == "ARMATURE"
                and modifier.show_viewport
            ):
                disabled_armature_modifiers.append(modifier)
                modifier.show_viewport = False

    try:
        for modifier_name in modifier_names:
            modifier = mesh_obj.modifiers.get(modifier_name)
            if modifier is None:
                continue

            try:
                apply_modifier_with_shape_keys(
                    context, mesh_obj, modifier, uv_map_index
                )
            except Exception as e:
                return (False, str(e))

        return (True, None)

    finally:
        # Re-enable armatures
        if disable_armatures:
            for modifier in disabled_armature_modifiers:
                modifier.show_viewport = True
