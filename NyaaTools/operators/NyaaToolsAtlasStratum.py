"""
Atlas Stratum Operators.

Operators for promoting/demoting materials between stratum levels,
moving materials to specific tiles, and managing atlas state.

These operators support undo via Blender's property system.
"""

import bpy
from bpy.props import IntProperty, StringProperty, BoolProperty


class NYAA_OT_AtlasPromoteStratum(bpy.types.Operator):
    """Promote material to higher resolution stratum (lower number)"""
    
    bl_idname = "nyaa.atlas_promote_stratum"
    bl_label = "Promote Stratum"
    bl_description = "Move material to higher resolution stratum (larger tile)"
    bl_options = {"REGISTER", "UNDO"}
    
    material_name: StringProperty(
        name="Material",
        description="Material to promote",
    )
    
    @classmethod
    def poll(cls, context):
        return True
    
    def execute(self, context):
        from ..atlas.stratum import promote_tile_coords, validate_tile_position
        
        # Find the asset config
        asset_config = self._get_asset_config(context)
        if not asset_config:
            self.report({"ERROR"}, "No active asset found")
            return {"CANCELLED"}
        
        atlas_config = asset_config.atlas_config
        
        # Find the material
        mat_entry = None
        for entry in atlas_config.materials:
            if entry.material_name == self.material_name:
                mat_entry = entry
                break
        
        if not mat_entry:
            self.report({"ERROR"}, f"Material '{self.material_name}' not found in atlas")
            return {"CANCELLED"}
        
        if mat_entry.stratum <= 0:
            self.report({"WARNING"}, "Already at maximum resolution (stratum 0)")
            return {"CANCELLED"}
        
        # Calculate new position
        try:
            new_stratum, new_tx, new_ty = promote_tile_coords(
                mat_entry.stratum, mat_entry.tile_x, mat_entry.tile_y
            )
        except ValueError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        
        # Check for conflicts
        if self._has_tile_conflict(atlas_config, new_stratum, new_tx, new_ty, self.material_name):
            self.report({"ERROR"}, f"Tile ({new_tx}, {new_ty}) at stratum {new_stratum} is occupied")
            return {"CANCELLED"}
        
        # Apply promotion
        mat_entry.stratum = new_stratum
        mat_entry.tile_x = new_tx
        mat_entry.tile_y = new_ty
        
        self._update_validation(atlas_config)
        
        self.report({"INFO"}, f"Promoted '{self.material_name}' to stratum {new_stratum}")
        return {"FINISHED"}
    
    def _get_asset_config(self, context):
        """Get the active asset config."""
        obj = context.active_object
        if obj and hasattr(obj, "nyaa_asset") and obj.nyaa_asset.is_asset:
            return obj.nyaa_asset
        return None
    
    def _has_tile_conflict(self, atlas_config, stratum, tile_x, tile_y, exclude_material):
        """Check if a tile is occupied by another material."""
        from ..atlas.stratum import stratum_to_scale, get_tile_bounds
        
        target_bounds = get_tile_bounds(stratum, tile_x, tile_y)
        
        for entry in atlas_config.materials:
            if entry.material_name == exclude_material:
                continue
            
            entry_bounds = get_tile_bounds(entry.stratum, entry.tile_x, entry.tile_y)
            
            # Check overlap
            if self._bounds_overlap(target_bounds, entry_bounds):
                return True
        
        return False
    
    def _bounds_overlap(self, bounds_a, bounds_b):
        """Check if two bounds rectangles overlap."""
        (a_min, a_max) = bounds_a
        (b_min, b_max) = bounds_b
        
        # No overlap if one is completely to the left/right/above/below
        if a_max[0] <= b_min[0] or b_max[0] <= a_min[0]:
            return False
        if a_max[1] <= b_min[1] or b_max[1] <= a_min[1]:
            return False
        
        return True
    
    def _update_validation(self, atlas_config):
        """Update validation state."""
        from ..atlas.stratum import StratumGrid
        
        grid = StratumGrid(max_stratum=atlas_config.max_stratum)
        has_overlaps = False
        
        for entry in atlas_config.materials:
            if not grid.occupy_tile(entry.stratum, entry.tile_x, entry.tile_y):
                has_overlaps = True
        
        atlas_config.has_overlaps = has_overlaps
        atlas_config.coverage = grid.calculate_coverage()


class NYAA_OT_AtlasDemoteStratum(bpy.types.Operator):
    """Demote material to lower resolution stratum (higher number)"""
    
    bl_idname = "nyaa.atlas_demote_stratum"
    bl_label = "Demote Stratum"
    bl_description = "Move material to lower resolution stratum (smaller tile)"
    bl_options = {"REGISTER", "UNDO"}
    
    material_name: StringProperty(
        name="Material",
        description="Material to demote",
    )
    
    @classmethod
    def poll(cls, context):
        return True
    
    def execute(self, context):
        from ..atlas.stratum import demote_tile_coords
        
        asset_config = self._get_asset_config(context)
        if not asset_config:
            self.report({"ERROR"}, "No active asset found")
            return {"CANCELLED"}
        
        atlas_config = asset_config.atlas_config
        
        mat_entry = None
        for entry in atlas_config.materials:
            if entry.material_name == self.material_name:
                mat_entry = entry
                break
        
        if not mat_entry:
            self.report({"ERROR"}, f"Material '{self.material_name}' not found in atlas")
            return {"CANCELLED"}
        
        if mat_entry.stratum >= atlas_config.max_stratum:
            self.report({"WARNING"}, f"Already at minimum resolution (stratum {atlas_config.max_stratum})")
            return {"CANCELLED"}
        
        try:
            new_stratum, new_tx, new_ty = demote_tile_coords(
                mat_entry.stratum, mat_entry.tile_x, mat_entry.tile_y,
                atlas_config.max_stratum
            )
        except ValueError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        
        # Check for conflicts
        if self._has_tile_conflict(atlas_config, new_stratum, new_tx, new_ty, self.material_name):
            self.report({"ERROR"}, f"Tile ({new_tx}, {new_ty}) at stratum {new_stratum} is occupied")
            return {"CANCELLED"}
        
        mat_entry.stratum = new_stratum
        mat_entry.tile_x = new_tx
        mat_entry.tile_y = new_ty
        
        self._update_validation(atlas_config)
        
        self.report({"INFO"}, f"Demoted '{self.material_name}' to stratum {new_stratum}")
        return {"FINISHED"}
    
    def _get_asset_config(self, context):
        obj = context.active_object
        if obj and hasattr(obj, "nyaa_asset") and obj.nyaa_asset.is_asset:
            return obj.nyaa_asset
        return None
    
    def _has_tile_conflict(self, atlas_config, stratum, tile_x, tile_y, exclude_material):
        from ..atlas.stratum import get_tile_bounds
        
        target_bounds = get_tile_bounds(stratum, tile_x, tile_y)
        
        for entry in atlas_config.materials:
            if entry.material_name == exclude_material:
                continue
            entry_bounds = get_tile_bounds(entry.stratum, entry.tile_x, entry.tile_y)
            if self._bounds_overlap(target_bounds, entry_bounds):
                return True
        return False
    
    def _bounds_overlap(self, bounds_a, bounds_b):
        (a_min, a_max) = bounds_a
        (b_min, b_max) = bounds_b
        if a_max[0] <= b_min[0] or b_max[0] <= a_min[0]:
            return False
        if a_max[1] <= b_min[1] or b_max[1] <= a_min[1]:
            return False
        return True
    
    def _update_validation(self, atlas_config):
        from ..atlas.stratum import StratumGrid
        grid = StratumGrid(max_stratum=atlas_config.max_stratum)
        has_overlaps = False
        for entry in atlas_config.materials:
            if not grid.occupy_tile(entry.stratum, entry.tile_x, entry.tile_y):
                has_overlaps = True
        atlas_config.has_overlaps = has_overlaps
        atlas_config.coverage = grid.calculate_coverage()


class NYAA_OT_AtlasMoveTile(bpy.types.Operator):
    """Move material to a specific tile position"""
    
    bl_idname = "nyaa.atlas_move_tile"
    bl_label = "Move to Tile"
    bl_description = "Move material to a specific stratum and tile position"
    bl_options = {"REGISTER", "UNDO"}
    
    material_name: StringProperty(
        name="Material",
        description="Material to move",
    )
    
    target_stratum: IntProperty(
        name="Stratum",
        default=0,
        min=0,
        max=8,
        description="Target stratum level",
    )
    
    target_tile_x: IntProperty(
        name="Tile X",
        default=0,
        min=0,
        description="Target X position",
    )
    
    target_tile_y: IntProperty(
        name="Tile Y",
        default=0,
        min=0,
        description="Target Y position",
    )
    
    @classmethod
    def poll(cls, context):
        return True
    
    def execute(self, context):
        from ..atlas.stratum import validate_tile_position, get_tile_bounds
        
        asset_config = self._get_asset_config(context)
        if not asset_config:
            self.report({"ERROR"}, "No active asset found")
            return {"CANCELLED"}
        
        atlas_config = asset_config.atlas_config
        
        # Validate target position
        if not validate_tile_position(self.target_stratum, self.target_tile_x, self.target_tile_y):
            self.report({"ERROR"}, f"Invalid tile position ({self.target_tile_x}, {self.target_tile_y}) for stratum {self.target_stratum}")
            return {"CANCELLED"}
        
        mat_entry = None
        for entry in atlas_config.materials:
            if entry.material_name == self.material_name:
                mat_entry = entry
                break
        
        if not mat_entry:
            self.report({"ERROR"}, f"Material '{self.material_name}' not found in atlas")
            return {"CANCELLED"}
        
        # Check for conflicts
        if self._has_tile_conflict(atlas_config, self.target_stratum, self.target_tile_x, self.target_tile_y, self.material_name):
            self.report({"ERROR"}, f"Tile ({self.target_tile_x}, {self.target_tile_y}) at stratum {self.target_stratum} is occupied")
            return {"CANCELLED"}
        
        mat_entry.stratum = self.target_stratum
        mat_entry.tile_x = self.target_tile_x
        mat_entry.tile_y = self.target_tile_y
        
        self._update_validation(atlas_config)
        
        self.report({"INFO"}, f"Moved '{self.material_name}' to ({self.target_tile_x}, {self.target_tile_y}) at stratum {self.target_stratum}")
        return {"FINISHED"}
    
    def _get_asset_config(self, context):
        obj = context.active_object
        if obj and hasattr(obj, "nyaa_asset") and obj.nyaa_asset.is_asset:
            return obj.nyaa_asset
        return None
    
    def _has_tile_conflict(self, atlas_config, stratum, tile_x, tile_y, exclude_material):
        from ..atlas.stratum import get_tile_bounds
        target_bounds = get_tile_bounds(stratum, tile_x, tile_y)
        for entry in atlas_config.materials:
            if entry.material_name == exclude_material:
                continue
            entry_bounds = get_tile_bounds(entry.stratum, entry.tile_x, entry.tile_y)
            if self._bounds_overlap(target_bounds, entry_bounds):
                return True
        return False
    
    def _bounds_overlap(self, bounds_a, bounds_b):
        (a_min, a_max) = bounds_a
        (b_min, b_max) = bounds_b
        if a_max[0] <= b_min[0] or b_max[0] <= a_min[0]:
            return False
        if a_max[1] <= b_min[1] or b_max[1] <= a_min[1]:
            return False
        return True
    
    def _update_validation(self, atlas_config):
        from ..atlas.stratum import StratumGrid
        grid = StratumGrid(max_stratum=atlas_config.max_stratum)
        has_overlaps = False
        for entry in atlas_config.materials:
            if not grid.occupy_tile(entry.stratum, entry.tile_x, entry.tile_y):
                has_overlaps = True
        atlas_config.has_overlaps = has_overlaps
        atlas_config.coverage = grid.calculate_coverage()


class NYAA_OT_AtlasRefreshMaterials(bpy.types.Operator):
    """Refresh atlas materials from asset meshes"""
    
    bl_idname = "nyaa.atlas_refresh_materials"
    bl_label = "Refresh Materials"
    bl_description = "Scan asset meshes and update material list"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and hasattr(obj, "nyaa_asset") and obj.nyaa_asset.is_asset
    
    def execute(self, context):
        from ..atlas.descriptors import build_material_descriptors
        from ..atlas.stratum import calculate_recommended_stratum
        
        asset_config = context.active_object.nyaa_asset
        atlas_config = asset_config.atlas_config
        
        # Get meshes from asset
        meshes = []
        for mesh_entry in asset_config.meshes:
            if mesh_entry.mesh_object and mesh_entry.mesh_object.type == "MESH":
                meshes.append(mesh_entry.mesh_object)
        
        if not meshes:
            self.report({"WARNING"}, "No meshes in asset")
            return {"CANCELLED"}
        
        # Build descriptors
        resolution = int(atlas_config.atlas_width)
        descriptors = build_material_descriptors(meshes, resolution, build_islands=False)
        
        # Track existing materials to preserve positions
        existing = {entry.material_name: entry for entry in atlas_config.materials}
        
        # Clear and rebuild
        atlas_config.materials.clear()
        
        for mat_name, desc in descriptors.items():
            entry = atlas_config.materials.add()
            entry.material_name = mat_name
            
            # Preserve existing position if available
            if mat_name in existing:
                old = existing[mat_name]
                entry.stratum = old.stratum
                entry.tile_x = old.tile_x
                entry.tile_y = old.tile_y
                entry.auto_stratum = old.auto_stratum
            else:
                entry.stratum = desc.recommended_stratum
                entry.tile_x = 0
                entry.tile_y = 0
                entry.auto_stratum = True
            
            entry.recommended_stratum = desc.recommended_stratum
            entry.total_uv_area = desc.total_uv_area
            entry.total_world_area = desc.total_world_area
            entry.significance = desc.significance
        
        self._update_validation(atlas_config)
        
        self.report({"INFO"}, f"Found {len(atlas_config.materials)} materials")
        return {"FINISHED"}
    
    def _update_validation(self, atlas_config):
        from ..atlas.stratum import StratumGrid
        grid = StratumGrid(max_stratum=atlas_config.max_stratum)
        has_overlaps = False
        for entry in atlas_config.materials:
            if not grid.occupy_tile(entry.stratum, entry.tile_x, entry.tile_y):
                has_overlaps = True
        atlas_config.has_overlaps = has_overlaps
        atlas_config.coverage = grid.calculate_coverage()


class NYAA_OT_AtlasAutoPlace(bpy.types.Operator):
    """Automatically place materials in the atlas grid"""
    
    bl_idname = "nyaa.atlas_auto_place"
    bl_label = "Auto-Place Materials"
    bl_description = "Automatically assign materials to tiles based on significance"
    bl_options = {"REGISTER", "UNDO"}
    
    use_recommended: BoolProperty(
        name="Use Recommended Stratum",
        default=True,
        description="Place each material at its recommended stratum level",
    )
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or not hasattr(obj, "nyaa_asset"):
            return False
        if not obj.nyaa_asset.is_asset:
            return False
        return len(obj.nyaa_asset.atlas_config.materials) > 0
    
    def execute(self, context):
        from ..atlas.stratum import StratumGrid
        
        atlas_config = context.active_object.nyaa_asset.atlas_config
        grid = StratumGrid(max_stratum=atlas_config.max_stratum)
        
        # Sort materials by significance (highest first)
        sorted_entries = sorted(
            atlas_config.materials,
            key=lambda e: e.significance,
            reverse=True
        )
        
        placed = 0
        for entry in sorted_entries:
            target_stratum = entry.recommended_stratum if self.use_recommended else entry.stratum
            
            # Find first free tile at target stratum
            free_tile = grid.find_free_tile(target_stratum)
            
            # If no free tile, try higher stratums
            while free_tile is None and target_stratum < atlas_config.max_stratum:
                target_stratum += 1
                free_tile = grid.find_free_tile(target_stratum)
            
            if free_tile:
                entry.stratum = target_stratum
                entry.tile_x, entry.tile_y = free_tile
                grid.occupy_tile(target_stratum, free_tile[0], free_tile[1])
                placed += 1
        
        atlas_config.has_overlaps = False
        atlas_config.coverage = grid.calculate_coverage()
        
        self.report({"INFO"}, f"Placed {placed}/{len(atlas_config.materials)} materials")
        return {"FINISHED"}


class NYAA_OT_AtlasValidate(bpy.types.Operator):
    """Validate atlas configuration for overlaps"""
    
    bl_idname = "nyaa.atlas_validate"
    bl_label = "Validate Atlas"
    bl_description = "Check for tile overlaps and update coverage"
    bl_options = {"REGISTER"}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and hasattr(obj, "nyaa_asset") and obj.nyaa_asset.is_asset
    
    def execute(self, context):
        from ..atlas.stratum import StratumGrid
        
        atlas_config = context.active_object.nyaa_asset.atlas_config
        grid = StratumGrid(max_stratum=atlas_config.max_stratum)
        
        overlaps = []
        for entry in atlas_config.materials:
            if not grid.occupy_tile(entry.stratum, entry.tile_x, entry.tile_y):
                overlaps.append(entry.material_name)
        
        atlas_config.has_overlaps = len(overlaps) > 0
        atlas_config.coverage = grid.calculate_coverage()
        
        if overlaps:
            self.report({"WARNING"}, f"Overlapping materials: {', '.join(overlaps)}")
        else:
            self.report({"INFO"}, f"No overlaps. Coverage: {atlas_config.coverage:.1%}")
        
        return {"FINISHED"}


# =============================================================================
# Registration
# =============================================================================


_classes = [
    NYAA_OT_AtlasPromoteStratum,
    NYAA_OT_AtlasDemoteStratum,
    NYAA_OT_AtlasMoveTile,
    NYAA_OT_AtlasRefreshMaterials,
    NYAA_OT_AtlasAutoPlace,
    NYAA_OT_AtlasValidate,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
