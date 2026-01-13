"""
Asset management operators for NyaaTools panel.
"""

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, StringProperty


def _any_mesh_is_ucx(meshes):
    """Check if any mesh in the list has a UCX_ name."""
    return any(m.name.upper().startswith("UCX_") for m in meshes)


def _validate_layer_name_ucx(layer_name, is_ue_collider):
    """
    Validate layer name vs collider flag.
    Returns (is_valid, error_message).
    """
    if layer_name.upper().startswith("UCX") and not is_ue_collider:
        return (
            False,
            "Layer names starting with 'UCX' are reserved. Use the UE Collider option instead.",
        )
    return True, ""


def _sort_asset_meshes(meshes_collection):
    """
    Sort meshes collection: non-colliders first (by layer, then name),
    then colliders last (by name).
    """

    def sort_key(entry):
        if entry.is_ue_collider:
            return (1, "", entry.mesh_object.name.lower() if entry.mesh_object else "")
        else:
            return (
                0,
                entry.layer_name.lower(),
                entry.mesh_object.name.lower() if entry.mesh_object else "",
            )

    # Selection sort using .move() - simple and correct
    n = len(meshes_collection)
    for target_pos in range(n):
        # Find the minimum element among positions target_pos to n-1
        min_idx = target_pos
        min_key = sort_key(meshes_collection[target_pos])
        for j in range(target_pos + 1, n):
            j_key = sort_key(meshes_collection[j])
            if j_key < min_key:
                min_idx = j
                min_key = j_key
        # Move the minimum to target_pos
        if min_idx != target_pos:
            meshes_collection.move(min_idx, target_pos)


from ..asset.asset_helpers import (
    get_asset_description,
    get_available_armatures_for_mesh,
    get_armature_from_mesh_modifiers,
)
from ..armature.estimate_humanoid_ratio import is_humanoid
from .panels_context import (
    SelectionContext,
    invalidate_selection_cache,
    tag_view3d_redraw,
)


def _get_armature_items_for_mesh(self, context):
    """Callback for dynamic enum items - builds list of armatures."""
    mesh = context.selected_objects[0] if context.selected_objects else None
    items = [("NONE", "None", "Create as static asset without armature")]

    if mesh is None or mesh.type != "MESH":
        return items

    armatures = get_available_armatures_for_mesh(mesh)

    modifier_armatures = [(a, is_asset) for a, is_asset, is_mod in armatures if is_mod]
    scene_armatures = [(a, is_asset) for a, is_asset, is_mod in armatures if not is_mod]

    if modifier_armatures:
        items.append(("", "From Modifiers", ""))
        for armature, is_asset in modifier_armatures:
            suffix = " [Already an asset]" if is_asset else ""
            items.append(
                (
                    armature.name,
                    armature.name + suffix,
                    f"Use armature: {armature.name}",
                )
            )

    if scene_armatures:
        items.append(("", "In Scene", ""))
        for armature, is_asset in scene_armatures:
            suffix = " [Already an asset]" if is_asset else ""
            items.append(
                (
                    armature.name,
                    armature.name + suffix,
                    f"Use armature: {armature.name}",
                )
            )

    return items


class NYAATOOLS_OT_MarkAsAsset(Operator):
    """Mark the selected object as an asset"""

    bl_idname = "nyaatools.mark_as_asset"
    bl_label = "Mark as Asset"
    bl_options = {"REGISTER", "UNDO"}

    asset_name: StringProperty(name="Asset Name", default="")

    @classmethod
    def poll(cls, context):
        if len(context.selected_objects) != 1:
            return False
        obj = context.selected_objects[0]
        return obj.type in ("ARMATURE", "MESH")

    def invoke(self, context, event):
        obj = context.selected_objects[0]
        if not self.asset_name:
            self.asset_name = obj.name
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        obj = context.selected_objects[0]
        desc = get_asset_description(obj)
        layout.label(text=f"This will create: {desc}", icon="INFO")
        layout.separator()
        layout.prop(self, "asset_name")

    def execute(self, context):
        obj = context.selected_objects[0]
        obj.nyaa_asset.is_asset = True
        obj.nyaa_asset.asset_name = self.asset_name
        # Pre-compute humanoid flag for armatures
        if obj.type == "ARMATURE":
            obj.nyaa_asset.is_humanoid = is_humanoid(obj)
        elif obj.type == "MESH":
            # For mesh assets, add host mesh as first entry
            entry = obj.nyaa_asset.meshes.add()
            entry.mesh_object = obj
            entry.layer_name = "Base"
        invalidate_selection_cache()
        tag_view3d_redraw(context)
        desc = get_asset_description(obj)
        self.report({"INFO"}, f"Marked '{obj.name}' as {desc}")
        return {"FINISHED"}


class NYAATOOLS_OT_UnmarkAsset(Operator):
    """Remove asset status from the selected object"""

    bl_idname = "nyaatools.unmark_asset"
    bl_label = "Destroy Asset"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        return sel.has_asset

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self, event, message="This will destroy Asset configuration for this asset"
        )

    def execute(self, context):
        sel = SelectionContext(context)
        obj = sel.asset
        if not obj:
            self.report({"ERROR"}, "No asset selected")
            return {"CANCELLED"}

        name = obj.nyaa_asset.asset_name
        obj.nyaa_asset.is_asset = False
        obj.nyaa_asset.is_humanoid = False
        obj.nyaa_asset.asset_name = ""
        obj.nyaa_asset.meshes.clear()
        invalidate_selection_cache()
        tag_view3d_redraw(context)
        self.report({"INFO"}, f"Removed asset status from '{name}'")
        return {"FINISHED"}


class NYAATOOLS_OT_ConfigureAsset(Operator):
    """Configure asset settings"""

    bl_idname = "nyaatools.configure_asset"
    bl_label = "Configure Asset"
    bl_options = {"REGISTER", "UNDO"}

    asset_name: StringProperty(name="Asset Name", default="")

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        return sel.has_asset

    def invoke(self, context, event):
        sel = SelectionContext(context)
        self.asset_name = sel.asset.nyaa_asset.asset_name
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        sel = SelectionContext(context)

        # Handle the case where the asset was destroyed via the child operator
        if not sel.has_asset or not sel.asset.nyaa_asset.is_asset:
            layout.label(text="Asset configuration has been removed.", icon="TRASH")
            layout.label(text="Click OK to dismiss this window.")
            return

        cfg = sel.asset.nyaa_asset
        layout.prop(self, "asset_name")

        box = layout.box()
        box.alert = True
        col = box.column(align=True)
        col.label(text="Danger Zone", icon="ERROR")
        col.operator("nyaatools.unmark_asset", text="Destroy Asset", icon="X")

    def execute(self, context):
        sel = SelectionContext(context)

        # If asset is gone (destroyed via button in this dialog), just finish
        if not sel.has_asset or not sel.asset.nyaa_asset.is_asset:
            return {"FINISHED"}

        cfg = sel.asset.nyaa_asset
        new_name = self.asset_name.strip()
        if not new_name:
            self.report({"ERROR"}, "Asset name cannot be empty")
            return {"CANCELLED"}

        if cfg.asset_name != new_name:
            cfg.asset_name = new_name
            self.report({"INFO"}, f"Updated asset name to '{new_name}'")
            tag_view3d_redraw(context)

        return {"FINISHED"}


class NYAATOOLS_OT_CreateAssetFromMesh(Operator):
    """Create an asset from selected mesh, optionally setting an armature"""

    bl_idname = "nyaatools.create_asset_from_mesh"
    bl_label = "Create Asset"
    bl_options = {"REGISTER", "UNDO"}

    asset_name: StringProperty(name="Asset Name", default="")
    armature_choice: EnumProperty(
        name="Armature",
        items=_get_armature_items_for_mesh,
        description="Armature to associate with this asset",
    )

    # Meta Objects
    show_meta_objects: BoolProperty(
        name="Meta Objects",
        default=False,
        description="Expand meta objects section",
    )
    is_ue_collider: BoolProperty(
        name="Unreal Engine Convex Collision",
        default=False,
        description="Mark as Unreal Engine convex-collision mesh (UCX_)",
    )

    @classmethod
    def poll(cls, context):
        if len(context.selected_objects) != 1:
            return False
        obj = context.selected_objects[0]
        if obj.type != "MESH":
            return False
        return not (hasattr(obj, "nyaa_asset") and obj.nyaa_asset.is_asset)

    def invoke(self, context, event):
        mesh = context.selected_objects[0]
        if not self.asset_name:
            self.asset_name = mesh.name

        modifier_armature = get_armature_from_mesh_modifiers(mesh)
        if modifier_armature:
            self.armature_choice = modifier_armature.name

        # Auto-expand meta objects and set collider flag if mesh is UCX_
        if mesh.name.upper().startswith("UCX_"):
            self.show_meta_objects = True
            self.is_ue_collider = True
        else:
            self.show_meta_objects = False
            self.is_ue_collider = False

        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        mesh = context.selected_objects[0]

        layout.prop(self, "asset_name")
        layout.separator()
        layout.prop(self, "armature_choice")
        layout.separator()

        # Check for UCX-only static asset error
        is_ucx_mesh = mesh.name.upper().startswith("UCX_")
        if self.armature_choice == "NONE" and is_ucx_mesh:
            err_box = layout.box()
            err_box.alert = True
            err_box.label(
                text="Cannot create asset from collision mesh alone.", icon="ERROR"
            )
            err_box.label(text="Select an armature or a non-UCX mesh.")
        elif self.armature_choice == "NONE":
            layout.label(text="This will create a static asset", icon="INFO")
        else:
            arm_obj = bpy.data.objects.get(self.armature_choice)
            if arm_obj:
                desc = get_asset_description(arm_obj)
                is_asset = (
                    arm_obj.nyaa_asset.is_asset
                    if hasattr(arm_obj, "nyaa_asset")
                    else False
                )
                if is_asset:
                    layout.label(text=f"Will add mesh to existing: {desc}", icon="INFO")
                else:
                    layout.label(text=f"This will create {desc}", icon="INFO")

        # Meta Objects section (collapsible) - only for armature-based assets
        if self.armature_choice != "NONE":
            layout.separator()
            box = layout.box()
            row = box.row()
            row.prop(
                self,
                "show_meta_objects",
                icon="TRIA_DOWN" if self.show_meta_objects else "TRIA_RIGHT",
                icon_only=True,
                emboss=False,
            )
            row.label(text="Meta Objects", icon="PHYSICS")

            if self.show_meta_objects:
                box.prop(self, "is_ue_collider")
                if self.is_ue_collider:
                    box.label(text="Layer will be set to 'UCX'", icon="INFO")

    def execute(self, context):
        mesh = context.selected_objects[0]
        is_ucx_mesh = mesh.name.upper().startswith("UCX_")

        # Block UCX-only static asset creation
        if self.armature_choice == "NONE" and is_ucx_mesh:
            self.report({"ERROR"}, "Cannot create asset from collision mesh alone")
            return {"CANCELLED"}

        # Determine layer name
        if self.is_ue_collider:
            layer_name = "UCX"
        else:
            layer_name = mesh.name

        if self.armature_choice == "NONE":
            mesh.nyaa_asset.is_asset = True
            mesh.nyaa_asset.asset_name = self.asset_name
            mesh.nyaa_asset.is_humanoid = False
            # Add host mesh as first entry (implicit "Base" layer)
            entry = mesh.nyaa_asset.meshes.add()
            entry.mesh_object = mesh
            entry.layer_name = "Base"
            invalidate_selection_cache()
            self.report({"INFO"}, f"Created static asset '{self.asset_name}'")
        else:
            arm_obj = bpy.data.objects.get(self.armature_choice)
            if not arm_obj:
                self.report({"ERROR"}, f"Armature '{self.armature_choice}' not found")
                return {"CANCELLED"}

            is_existing_asset = (
                arm_obj.nyaa_asset.is_asset if hasattr(arm_obj, "nyaa_asset") else False
            )

            if is_existing_asset:
                cfg = arm_obj.nyaa_asset
                already_exists = any(entry.mesh_object == mesh for entry in cfg.meshes)
                if not already_exists:
                    entry = cfg.meshes.add()
                    entry.mesh_object = mesh
                    entry.layer_name = layer_name
                    entry.is_ue_collider = self.is_ue_collider
                _sort_asset_meshes(cfg.meshes)
                invalidate_selection_cache()
                self.report(
                    {"INFO"}, f"Added mesh to existing asset '{cfg.asset_name}'"
                )
            else:
                arm_obj.nyaa_asset.is_asset = True
                arm_obj.nyaa_asset.asset_name = self.asset_name
                arm_obj.nyaa_asset.is_humanoid = is_humanoid(arm_obj)
                entry = arm_obj.nyaa_asset.meshes.add()
                entry.mesh_object = mesh
                entry.layer_name = layer_name
                entry.is_ue_collider = self.is_ue_collider
                _sort_asset_meshes(arm_obj.nyaa_asset.meshes)
                invalidate_selection_cache()
                desc = get_asset_description(arm_obj)
                self.report({"INFO"}, f"Created {desc} '{self.asset_name}' with mesh")
        tag_view3d_redraw(context)
        return {"FINISHED"}


class NYAATOOLS_OT_JumpToAsset(Operator):
    """Select the asset that owns this mesh"""

    bl_idname = "nyaatools.jump_to_asset"
    bl_label = "Jump to Asset"
    bl_options = {"REGISTER", "UNDO"}

    asset_name: StringProperty(name="Asset Object Name", default="")

    def execute(self, context):
        if not self.asset_name:
            self.report({"ERROR"}, "No asset specified")
            return {"CANCELLED"}

        obj = bpy.data.objects.get(self.asset_name)
        if not obj:
            self.report({"ERROR"}, f"Asset '{self.asset_name}' not found")
            return {"CANCELLED"}

        # Auto-show the asset by enabling/unhiding its collections
        obj.hide_viewport = False
        obj.hide_set(False)

        for collection in obj.users_collection:
            collection.hide_viewport = False
            collection.hide_render = False

            layer_collection = self._find_layer_collection(
                context.view_layer.layer_collection, collection.name
            )
            if layer_collection:
                layer_collection.exclude = False
                layer_collection.hide_viewport = False

        # Add asset to selection and make it active
        obj.select_set(True)
        context.view_layer.objects.active = obj

        invalidate_selection_cache()
        tag_view3d_redraw(context)

        self.report({"INFO"}, f"Added asset '{obj.nyaa_asset.asset_name}' to selection")
        return {"FINISHED"}

    def _find_layer_collection(self, layer_collection, name):
        """Recursively find a LayerCollection by name."""
        if layer_collection.name == name:
            return layer_collection
        for child in layer_collection.children:
            result = self._find_layer_collection(child, name)
            if result:
                return result
        return None


class NYAATOOLS_OT_JumpToMesh(Operator):
    """Select the active mesh from the asset's mesh list"""

    bl_idname = "nyaatools.jump_to_mesh"
    bl_label = "Jump to Mesh"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        if not sel.has_asset:
            return False
        cfg = sel.asset.nyaa_asset
        if len(cfg.meshes) == 0:
            return False
        if cfg.active_mesh_index < 0 or cfg.active_mesh_index >= len(cfg.meshes):
            return False
        entry = cfg.meshes[cfg.active_mesh_index]
        return entry.mesh_object is not None

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        entry = cfg.meshes[cfg.active_mesh_index]

        if not entry.mesh_object:
            self.report({"ERROR"}, "Mesh object is None (deleted)")
            return {"CANCELLED"}

        mesh_obj = entry.mesh_object

        # Auto-show the mesh by enabling/unhiding its collections
        mesh_obj.hide_viewport = False
        mesh_obj.hide_set(False)

        for collection in mesh_obj.users_collection:
            collection.hide_viewport = False
            collection.hide_render = False

            layer_collection = self._find_layer_collection(
                context.view_layer.layer_collection, collection.name
            )
            if layer_collection:
                layer_collection.exclude = False
                layer_collection.hide_viewport = False

        # Deselect all and select the mesh
        bpy.ops.object.select_all(action="DESELECT")
        mesh_obj.select_set(True)
        context.view_layer.objects.active = mesh_obj

        invalidate_selection_cache()
        tag_view3d_redraw(context)

        self.report({"INFO"}, f"Selected mesh '{mesh_obj.name}'")
        return {"FINISHED"}

    def _find_layer_collection(self, layer_collection, name):
        """Recursively find a LayerCollection by name."""
        if layer_collection.name == name:
            return layer_collection
        for child in layer_collection.children:
            result = self._find_layer_collection(child, name)
            if result:
                return result
        return None


def _get_existing_layer_items(self, context):
    """Callback for dynamic enum items - builds list of existing layers."""
    sel = SelectionContext(context)
    if not sel.asset:
        return [("Base", "Base", "Default layer")]

    cfg = sel.asset.nyaa_asset
    layer_names = set()
    for entry in cfg.meshes:
        if entry.layer_name:
            layer_names.add(entry.layer_name)

    if not layer_names:
        return [("Base", "Base", "Default layer")]

    items = []
    for name in sorted(layer_names):
        items.append((name, name, f"Add to existing layer: {name}"))
    return items


class NYAATOOLS_OT_AddSelectedMeshes(Operator):
    """Add selected meshes to the asset"""

    bl_idname = "nyaatools.add_selected_meshes"
    bl_label = "Add Selected Meshes"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(
        name="Mode",
        items=[
            ("EXISTING", "Existing Layer", "Add to an existing layer"),
            ("NEW", "New Layer", "Create a new layer"),
        ],
        default="EXISTING",
    )
    existing_layer: EnumProperty(
        name="Layer",
        items=_get_existing_layer_items,
        description="Select an existing layer",
    )
    new_layer_name: StringProperty(name="Layer Name", default="")

    # Meta Objects
    show_meta_objects: BoolProperty(
        name="Meta Objects",
        default=False,
        description="Expand meta objects section",
    )
    is_ue_collider: BoolProperty(
        name="Unreal Engine Convex Collision",
        default=False,
        description="Mark as Unreal Engine convex-collision mesh (UCX_)",
    )

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        return sel.has_meshes_for_asset

    def invoke(self, context, event):
        sel = SelectionContext(context)
        # Filter out host mesh if asset is mesh-hosted
        meshes_to_add = sel.meshes
        if sel.asset and sel.asset.type == "MESH":
            meshes_to_add = [m for m in sel.meshes if m != sel.asset]

        # Default new layer name to mesh name if single mesh
        if len(meshes_to_add) == 1:
            self.new_layer_name = meshes_to_add[0].name
        else:
            self.new_layer_name = "Layer Name"

        # Auto-expand meta objects and set collider flag if any mesh is UCX_
        if _any_mesh_is_ucx(meshes_to_add):
            self.show_meta_objects = True
            self.is_ue_collider = True
        else:
            self.show_meta_objects = False
            self.is_ue_collider = False

        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        sel = SelectionContext(context)

        # Filter out host mesh if asset is mesh-hosted
        meshes_to_add = sel.meshes
        if sel.asset and sel.asset.type == "MESH":
            meshes_to_add = [m for m in sel.meshes if m != sel.asset]

        # Show meshes to be added
        box = layout.box()
        box.label(text="Meshes to add:", icon="OUTLINER_OB_MESH")
        for mesh in meshes_to_add:
            box.label(text=f"  {mesh.name}")

        # Layer selection (hidden if collider)
        if not self.is_ue_collider:
            layout.separator()
            layout.prop(self, "mode", expand=True)
            layout.separator()

            if self.mode == "EXISTING":
                layout.prop(self, "existing_layer")
            else:
                layout.prop(self, "new_layer_name", text="Name")

            # Validate layer name
            layer_name = (
                self.existing_layer if self.mode == "EXISTING" else self.new_layer_name
            )
            is_valid, error = _validate_layer_name_ucx(layer_name, self.is_ue_collider)
            if not is_valid:
                err_box = layout.box()
                err_box.alert = True
                err_box.label(text=error, icon="ERROR")

        # Meta Objects section (collapsible)
        layout.separator()
        box = layout.box()
        row = box.row()
        row.prop(
            self,
            "show_meta_objects",
            icon="TRIA_DOWN" if self.show_meta_objects else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        row.label(text="Meta Objects", icon="PHYSICS")

        if self.show_meta_objects:
            box.prop(self, "is_ue_collider")
            if self.is_ue_collider:
                box.label(text="Layer will be set to 'UCX'", icon="INFO")

    def execute(self, context):
        sel = SelectionContext(context)
        if not sel.asset:
            self.report({"ERROR"}, "No asset selected")
            return {"CANCELLED"}

        cfg = sel.asset.nyaa_asset

        # Determine the layer name
        if self.is_ue_collider:
            layer_name = "UCX"
        elif self.mode == "EXISTING":
            layer_name = self.existing_layer
        else:
            layer_name = self.new_layer_name.strip()
            if not layer_name:
                self.report({"ERROR"}, "Layer name cannot be empty")
                return {"CANCELLED"}

        # Validate layer name
        is_valid, error = _validate_layer_name_ucx(layer_name, self.is_ue_collider)
        if not is_valid:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        # Filter out host mesh if asset is mesh-hosted
        meshes_to_add = sel.meshes
        if sel.asset.type == "MESH":
            meshes_to_add = [m for m in sel.meshes if m != sel.asset]

        added = 0

        for mesh in meshes_to_add:
            already_exists = any(entry.mesh_object == mesh for entry in cfg.meshes)
            if already_exists:
                continue
            entry = cfg.meshes.add()
            entry.mesh_object = mesh
            entry.layer_name = layer_name
            entry.is_ue_collider = self.is_ue_collider
            added += 1

        if added > 0:
            _sort_asset_meshes(cfg.meshes)
            tag_view3d_redraw(context)
        self.report({"INFO"}, f"Added {added} mesh(es) to layer '{layer_name}'")
        return {"FINISHED"}


class NYAATOOLS_OT_RemoveMesh(Operator):
    """Remove the active mesh from the asset's mesh list"""

    bl_idname = "nyaatools.remove_mesh"
    bl_label = "Remove Mesh"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        if not sel.has_asset:
            return False
        cfg = sel.asset.nyaa_asset
        if len(cfg.meshes) == 0:
            return False
        if cfg.active_mesh_index < 0 or cfg.active_mesh_index >= len(cfg.meshes):
            return False
        # For mesh-hosted assets, cannot remove the host (index 0)
        if sel.asset.type == "MESH" and cfg.active_mesh_index == 0:
            return False
        return True

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        idx = cfg.active_mesh_index

        mesh_name = (
            cfg.meshes[idx].mesh_object.name
            if cfg.meshes[idx].mesh_object
            else "(deleted)"
        )
        cfg.meshes.remove(idx)

        if cfg.active_mesh_index >= len(cfg.meshes) and len(cfg.meshes) > 0:
            cfg.active_mesh_index = len(cfg.meshes) - 1

        tag_view3d_redraw(context)
        self.report({"INFO"}, f"Removed '{mesh_name}' from asset")
        return {"FINISHED"}


class NYAATOOLS_OT_RemoveSelectedMeshes(Operator):
    """Remove currently selected meshes from the asset"""

    bl_idname = "nyaatools.remove_selected_meshes"
    bl_label = "Remove Selected from Asset"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        return sel.has_meshes_for_asset

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        removed = 0

        mesh_set = set(sel.meshes)
        indices_to_remove = []

        for i, entry in enumerate(cfg.meshes):
            if entry.mesh_object in mesh_set:
                indices_to_remove.append(i)

        for idx in reversed(indices_to_remove):
            cfg.meshes.remove(idx)
            removed += 1

        if cfg.active_mesh_index >= len(cfg.meshes) and len(cfg.meshes) > 0:
            cfg.active_mesh_index = len(cfg.meshes) - 1

        if removed > 0:
            tag_view3d_redraw(context)
        self.report({"INFO"}, f"Removed {removed} mesh(es) from asset")
        return {"FINISHED"}


def _get_existing_layer_items_for_edit(self, context):
    """Callback for dynamic enum items - builds list of layers with 1+ usage (excluding current entry)."""
    sel = SelectionContext(context)
    if not sel.asset:
        return [("Base", "Base", "Default layer")]

    cfg = sel.asset.nyaa_asset
    if cfg.active_mesh_index < 0 or cfg.active_mesh_index >= len(cfg.meshes):
        return [("Base", "Base", "Default layer")]

    current_entry = cfg.meshes[cfg.active_mesh_index]

    # Count layer usages excluding the current entry
    layer_counts = {}
    for i, entry in enumerate(cfg.meshes):
        if i == cfg.active_mesh_index:
            continue
        name = entry.layer_name
        if name:
            layer_counts[name] = layer_counts.get(name, 0) + 1

    # Only include layers that have 1+ other meshes
    items = []
    for name in sorted(layer_counts.keys()):
        items.append((name, name, f"Move to layer: {name}"))

    if not items:
        return [("__NONE__", "(No other layers)", "No existing layers to choose from")]

    return items


class NYAATOOLS_OT_EditMeshEntry(Operator):
    """Edit the layer name of the selected mesh entry"""

    bl_idname = "nyaatools.edit_mesh_entry"
    bl_label = "Edit Mesh Entry"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(
        name="Mode",
        items=[
            ("EXISTING", "Existing Layer", "Move to an existing layer"),
            ("NEW", "New Layer", "Create or rename to a new layer"),
        ],
        default="NEW",
    )
    existing_layer: EnumProperty(
        name="Layer",
        items=_get_existing_layer_items_for_edit,
        description="Select an existing layer",
    )
    new_layer_name: StringProperty(name="Rename", default="")

    # Meta Objects
    show_meta_objects: BoolProperty(
        name="Meta Objects",
        default=False,
        description="Expand meta objects section",
    )
    is_ue_collider: BoolProperty(
        name="Unreal Engine Convex Collision",
        default=False,
        description="Mark as Unreal Engine convex-collision mesh (UCX_)",
    )

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        if not sel.has_asset:
            return False
        cfg = sel.asset.nyaa_asset
        return len(cfg.meshes) > 0 and 0 <= cfg.active_mesh_index < len(cfg.meshes)

    def invoke(self, context, event):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        entry = cfg.meshes[cfg.active_mesh_index]
        current_layer = entry.layer_name

        # Load current collider state
        self.is_ue_collider = entry.is_ue_collider

        # Auto-expand meta objects if entry is a collider
        self.show_meta_objects = entry.is_ue_collider

        # Count how many OTHER meshes use the same layer name
        other_count = sum(
            1
            for i, e in enumerate(cfg.meshes)
            if i != cfg.active_mesh_index and e.layer_name == current_layer
        )

        # Prefill the new layer name with current
        self.new_layer_name = current_layer

        if other_count >= 1:
            # Others share this layer → default to Existing tab with this layer selected
            self.mode = "EXISTING"
            self.existing_layer = current_layer
        else:
            # Unique layer → default to New tab (rename mode)
            self.mode = "NEW"

        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout

        # Layer selection (hidden if collider)
        if not self.is_ue_collider:
            layout.prop(self, "mode", expand=True)
            layout.separator()

            if self.mode == "EXISTING":
                # Check if there are any valid existing layers
                items = _get_existing_layer_items_for_edit(self, context)
                if items and items[0][0] == "__NONE__":
                    layout.label(text="No other layers available", icon="INFO")
                else:
                    layout.prop(self, "existing_layer")
            else:
                layout.prop(self, "new_layer_name", text="Rename")

            # Validate layer name
            layer_name = (
                self.existing_layer if self.mode == "EXISTING" else self.new_layer_name
            )
            is_valid, error = _validate_layer_name_ucx(layer_name, self.is_ue_collider)
            if not is_valid:
                err_box = layout.box()
                err_box.alert = True
                err_box.label(text=error, icon="ERROR")

        # Meta Objects section (collapsible)
        layout.separator()
        box = layout.box()
        row = box.row()
        row.prop(
            self,
            "show_meta_objects",
            icon="TRIA_DOWN" if self.show_meta_objects else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        row.label(text="Meta Objects", icon="PHYSICS")

        if self.show_meta_objects:
            box.prop(self, "is_ue_collider")
            if self.is_ue_collider:
                box.label(text="Layer will be set to 'UCX'", icon="INFO")

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        entry = cfg.meshes[cfg.active_mesh_index]

        # Determine layer name
        if self.is_ue_collider:
            layer_name = "UCX"
        elif self.mode == "EXISTING":
            # Check for the placeholder value
            if self.existing_layer == "__NONE__":
                self.report({"ERROR"}, "No existing layer selected")
                return {"CANCELLED"}
            layer_name = self.existing_layer
        else:
            layer_name = self.new_layer_name.strip()
            if not layer_name:
                self.report({"ERROR"}, "Layer name cannot be empty")
                return {"CANCELLED"}

        # Validate layer name
        is_valid, error = _validate_layer_name_ucx(layer_name, self.is_ue_collider)
        if not is_valid:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        entry.layer_name = layer_name
        entry.is_ue_collider = self.is_ue_collider
        _sort_asset_meshes(cfg.meshes)
        tag_view3d_redraw(context)
        self.report({"INFO"}, f"Updated layer to '{layer_name}'")
        return {"FINISHED"}


class NYAATOOLS_OT_RenameLayer(Operator):
    """Rename the layer of the active mesh entry"""

    bl_idname = "nyaatools.rename_layer"
    bl_label = "Rename Layer"
    bl_options = {"REGISTER", "UNDO"}

    new_layer_name: StringProperty(name="New Layer Name", default="")

    @classmethod
    def poll(cls, context):
        sel = SelectionContext(context)
        if not sel.has_asset:
            return False
        cfg = sel.asset.nyaa_asset
        return len(cfg.meshes) > 0 and 0 <= cfg.active_mesh_index < len(cfg.meshes)

    def invoke(self, context, event):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        entry = cfg.meshes[cfg.active_mesh_index]
        self.new_layer_name = entry.layer_name
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        entry = cfg.meshes[cfg.active_mesh_index]
        current_layer = entry.layer_name

        layout.prop(self, "new_layer_name", text="New Name")

        new_name = self.new_layer_name.strip()
        if not new_name:
            err_box = layout.box()
            err_box.alert = True
            err_box.label(text="Layer name cannot be empty", icon="ERROR")
            return

        if new_name == current_layer:
            return

        # Check if new name collides with another layer (excluding current layer)
        other_layers = set()
        for e in cfg.meshes:
            if e.layer_name != current_layer:
                other_layers.add(e.layer_name)

        if new_name in other_layers:
            warn_box = layout.box()
            warn_box.alert = True
            warn_box.label(text="Warning: Layer name collision", icon="ERROR")
            warn_box.label(text=f"Layer '{new_name}' already exists")
            warn_box.label(text="This will merge layers", icon="INFO")

        # Validate layer name format
        is_valid, error = _validate_layer_name_ucx(new_name, entry.is_ue_collider)
        if not is_valid:
            err_box = layout.box()
            err_box.alert = True
            err_box.label(text=error, icon="ERROR")

    def execute(self, context):
        sel = SelectionContext(context)
        cfg = sel.asset.nyaa_asset
        entry = cfg.meshes[cfg.active_mesh_index]
        current_layer = entry.layer_name

        new_name = self.new_layer_name.strip()
        if not new_name:
            self.report({"ERROR"}, "Layer name cannot be empty")
            return {"CANCELLED"}

        if new_name == current_layer:
            self.report({"INFO"}, "Layer name unchanged")
            return {"FINISHED"}

        # Validate layer name format
        is_valid, error = _validate_layer_name_ucx(new_name, entry.is_ue_collider)
        if not is_valid:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        # Rename all meshes in the current layer to the new name
        renamed_count = 0
        for e in cfg.meshes:
            if e.layer_name == current_layer:
                e.layer_name = new_name
                renamed_count += 1

        _sort_asset_meshes(cfg.meshes)
        tag_view3d_redraw(context)

        if renamed_count > 1:
            self.report(
                {"INFO"},
                f"Renamed layer '{current_layer}' to '{new_name}' ({renamed_count} meshes)",
            )
        else:
            self.report({"INFO"}, f"Renamed layer '{current_layer}' to '{new_name}'")

        return {"FINISHED"}
