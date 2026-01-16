"""
Atlas Recombination Operators.

Operators for executing atlas capture, transform, and recombination workflows.
These are the action operators that perform the actual atlas baking.
"""

import bpy
import os
import time
import tempfile
import json
from bpy.props import BoolProperty, StringProperty, EnumProperty


class NYAA_OT_AtlasCapturePreview(bpy.types.Operator):
    """Capture material previews for atlas visualization"""
    
    bl_idname = "nyaa.atlas_capture_preview"
    bl_label = "Capture Previews"
    bl_description = "Bake small preview textures for each material"
    bl_options = {"REGISTER", "UNDO"}
    
    preview_size: EnumProperty(
        name="Preview Size",
        items=[
            ("128", "128px", "128x128 preview"),
            ("256", "256px", "256x256 preview"),
            ("512", "512px", "512x512 preview"),
        ],
        default="256",
        description="Preview texture resolution",
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
        from ..atlas.capture_bake import capture_single_material
        from ..atlas.descriptors import MaterialDescriptor
        
        asset_config = context.active_object.nyaa_asset
        atlas_config = asset_config.atlas_config
        
        resolution = (int(self.preview_size), int(self.preview_size))
        
        # Get meshes
        meshes = []
        for mesh_entry in asset_config.meshes:
            if mesh_entry.mesh_object and mesh_entry.mesh_object.type == "MESH":
                meshes.append(mesh_entry.mesh_object)
        
        if not meshes:
            self.report({"ERROR"}, "No meshes in asset")
            return {"CANCELLED"}
        
        captured = 0
        for entry in atlas_config.materials:
            # Build a temporary descriptor
            desc = MaterialDescriptor(
                material_name=entry.material_name,
                source_mesh_names=[m.name for m in meshes],
            )
            
            # Capture just diffuse for preview
            result = capture_single_material(
                desc,
                ["rgba"],
                resolution,
                print,
            )
            
            if result:
                captured += 1
        
        self.report({"INFO"}, f"Captured {captured} previews")
        return {"FINISHED"}


class NYAA_OT_AtlasApplyTransforms(bpy.types.Operator):
    """Apply atlas UV transforms to meshes"""
    
    bl_idname = "nyaa.atlas_apply_transforms"
    bl_label = "Apply Atlas UVs"
    bl_description = "Create and transform '-- Atlas' UV layer based on stratum positions"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or not hasattr(obj, "nyaa_asset"):
            return False
        if not obj.nyaa_asset.is_asset:
            return False
        atlas_config = obj.nyaa_asset.atlas_config
        return len(atlas_config.materials) > 0 and not atlas_config.has_overlaps
    
    def execute(self, context):
        from ..atlas.recombine import (
            copy_uvs_to_atlas_layer,
            transform_atlas_uvs_for_material,
            ATLAS_UV_NAME,
        )
        
        asset_config = context.active_object.nyaa_asset
        atlas_config = asset_config.atlas_config
        
        # Get all unique meshes
        meshes = set()
        for mesh_entry in asset_config.meshes:
            if mesh_entry.mesh_object and mesh_entry.mesh_object.type == "MESH":
                meshes.add(mesh_entry.mesh_object)
        
        if not meshes:
            self.report({"ERROR"}, "No meshes in asset")
            return {"CANCELLED"}
        
        # Create atlas UV layers
        for mesh in meshes:
            copy_uvs_to_atlas_layer(mesh, "UVMap")
        
        # Apply transforms per material
        transformed = 0
        for entry in atlas_config.materials:
            for mesh in meshes:
                if transform_atlas_uvs_for_material(
                    mesh,
                    entry.material_name,
                    entry.stratum,
                    entry.tile_x,
                    entry.tile_y,
                    print,
                ):
                    transformed += 1
        
        self.report({"INFO"}, f"Applied atlas transforms ({transformed} material/mesh pairs)")
        return {"FINISHED"}


class NYAA_OT_AtlasRemoveTransforms(bpy.types.Operator):
    """Remove atlas UV layers from meshes"""
    
    bl_idname = "nyaa.atlas_remove_transforms"
    bl_label = "Remove Atlas UVs"
    bl_description = "Remove '-- Atlas' UV layer from all asset meshes"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and hasattr(obj, "nyaa_asset") and obj.nyaa_asset.is_asset
    
    def execute(self, context):
        from ..atlas.recombine import ATLAS_UV_NAME
        
        asset_config = context.active_object.nyaa_asset
        
        removed = 0
        for mesh_entry in asset_config.meshes:
            mesh = mesh_entry.mesh_object
            if not mesh or mesh.type != "MESH":
                continue
            
            if ATLAS_UV_NAME in mesh.data.uv_layers:
                mesh.data.uv_layers.remove(mesh.data.uv_layers[ATLAS_UV_NAME])
                removed += 1
        
        self.report({"INFO"}, f"Removed {removed} atlas UV layers")
        return {"FINISHED"}


class NYAA_OT_AtlasExecuteRecombination(bpy.types.Operator):
    """Execute full atlas recombination and bake"""
    
    bl_idname = "nyaa.atlas_execute_recombination"
    bl_label = "Execute Recombination"
    bl_description = "Capture, transform, merge, and bake atlas textures"
    bl_options = {"REGISTER", "UNDO"}
    
    stop_after_shader: BoolProperty(
        name="Debug: Stop After Shader",
        default=False,
        description="Stop after building recombination shader (for debugging)",
    )
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or not hasattr(obj, "nyaa_asset"):
            return False
        if not obj.nyaa_asset.is_asset:
            return False
        atlas_config = obj.nyaa_asset.atlas_config
        return atlas_config.enabled and len(atlas_config.materials) > 0 and not atlas_config.has_overlaps
    
    def execute(self, context):
        from ..atlas.descriptors import build_atlas_descriptor, MaterialDescriptor
        from ..atlas.capture_bake import capture_material_bakes
        from ..atlas.recombine import execute_atlas_recombination
        
        asset_config = context.active_object.nyaa_asset
        atlas_config = asset_config.atlas_config
        
        # Get meshes
        meshes = []
        for mesh_entry in asset_config.meshes:
            if mesh_entry.mesh_object and mesh_entry.mesh_object.type == "MESH":
                meshes.append(mesh_entry.mesh_object)
        
        if not meshes:
            self.report({"ERROR"}, "No meshes in asset")
            return {"CANCELLED"}
        
        # Build atlas descriptor from PropertyGroup config
        atlas = build_atlas_descriptor(
            meshes,
            int(atlas_config.atlas_width),
            int(atlas_config.atlas_height),
            asset_config.asset_name,
            auto_place=False,
        )
        
        # Apply stratum positions from PropertyGroup
        for entry in atlas_config.materials:
            if entry.material_name in atlas.materials:
                mat_desc = atlas.materials[entry.material_name]
                mat_desc.stratum = entry.stratum
                mat_desc.tile_x = entry.tile_x
                mat_desc.tile_y = entry.tile_y
        
        # Determine bake formats from asset config
        bake_formats = []
        for bake_img in asset_config.bake_images:
            if bake_img.format not in bake_formats:
                bake_formats.append(bake_img.format)
        
        if not bake_formats:
            bake_formats = ["rgba"]  # Default
        
        # Capture material bakes
        self.report({"INFO"}, "Capturing material bakes...")
        capture_material_bakes(atlas, bake_formats, None, print)
        
        # Execute recombination
        self.report({"INFO"}, "Executing recombination...")
        results = execute_atlas_recombination(
            atlas,
            bake_formats,
            (int(atlas_config.atlas_width), int(atlas_config.atlas_height)),
            print,
            self.stop_after_shader,
        )
        
        if self.stop_after_shader:
            self.report({"INFO"}, "Stopped after shader setup (debug mode)")
            return {"FINISHED"}
        
        if results:
            self.report({"INFO"}, f"Recombination complete: {len(results)} atlas textures")
        else:
            self.report({"WARNING"}, "Recombination produced no results")
        
        return {"FINISHED"}


class NYAA_OT_AtlasBuildShaderPreview(bpy.types.Operator):
    """Build recombination shader for preview without baking"""
    
    bl_idname = "nyaa.atlas_build_shader_preview"
    bl_label = "Build Preview Shader"
    bl_description = "Create the recombination shader for material preview"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or not hasattr(obj, "nyaa_asset"):
            return False
        return obj.nyaa_asset.is_asset
    
    def execute(self, context):
        from ..atlas.recombine import build_recombination_shader
        from ..atlas.descriptors import MaterialDescriptor
        
        asset_config = context.active_object.nyaa_asset
        atlas_config = asset_config.atlas_config
        
        # Create temp material
        import random
        temp_name = f"__atlas_preview_{random.randint(1000, 9999)}"
        temp_material = bpy.data.materials.new(name=temp_name)
        temp_material.use_nodes = True
        
        # Build descriptors list
        descriptors = []
        for entry in atlas_config.materials:
            desc = MaterialDescriptor(
                material_name=entry.material_name,
                stratum=entry.stratum,
                tile_x=entry.tile_x,
                tile_y=entry.tile_y,
            )
            descriptors.append(desc)
        
        # Build shader (without captured images - for structure preview)
        build_recombination_shader(temp_material, descriptors, print)
        
        self.report({"INFO"}, f"Created preview shader: {temp_name}")
        return {"FINISHED"}


# =============================================================================
# Registration
# =============================================================================


_classes = [
    NYAA_OT_AtlasCapturePreview,
    NYAA_OT_AtlasApplyTransforms,
    NYAA_OT_AtlasRemoveTransforms,
    NYAA_OT_AtlasExecuteRecombination,
    NYAA_OT_AtlasBuildShaderPreview,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
