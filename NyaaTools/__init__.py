import inspect
import bpy

from . import dev_reload
from .asset import asset_registry


bl_info = {
    "name": "NyaaTools",
    "author": "Nyaarium",
    "blender": (5, 0, 1),
    "version": (2, 2, 1),
    "description": "Various Nyaarium tools for mesh cleanup, merging, and exporting assets",
    "location": "N-Panel > NyaaTools",
    "category": "Object",
}


# Track if we've registered before (for hot reload)
_has_registered = False


def _toggle_register(reg: bool):
    """Register (reg=True) or unregister (reg=False) all classes."""
    global _has_registered

    if reg:
        # Hot reload: if re-enabling addon, reload all submodules from disk first
        if _has_registered:
            dev_reload.reload_submodules()
        _has_registered = True

    # Operators
    from .operators import NyaaToolsAddModifier
    from .operators import NyaaToolsCheckImageFormats
    from .operators import NyaaToolsDissolveBones
    from .operators import NyaaToolsHelpImageFormat
    from .operators import NyaaToolsImagePacker
    from .operators import NyaaToolsMeshCleanup
    from .operators import NyaaToolsMergeArmatures
    from .operators import NyaaToolsNormalizeArmatureATPose
    from .operators import NyaaToolsNormalizeArmatureClearCustomObjects
    from .operators import NyaaToolsNormalizeArmatureRename
    from .operators import NyaaToolsNormalizeArmatureRetarget
    from .operators import NyaaToolsRenamePackedImage
    from .operators import NyaaSelectStandardBones
    from .operators import PrzemirApplyTopModifier
    from .operators.merge_export import operator as merge_export_op
    from .operators.bake import operator as bake_op

    # Panel operators
    from .panels import LinkButton
    from .panels import operators_asset
    from .panels import operators_export
    from .panels import operators_bake
    from .panels import operators_migrate

    # UI Lists
    from .panels import panels_uilists

    # Panels
    from .panels import panels_main
    from .panels import panels_utils

    # UI
    from .ui import ProgressManager

    # Import PropertyGroup classes directly
    from .types.asset_types import (
        NyaaAssetMeshEntry,
        NyaaBakeImage,
        NyaaExportProfile,
        NyaaAssetConfig,
    )
    from .types.prop_types import NyaaPropConfig
    from .types.settings_types import (
        NyaaToolsBakeSettings,
        NyaaToolsExportSettings,
        NyaaToolsSettings,
    )

    # All items in registration order (by dependency/importance)
    # Items can be:
    # - Classes (registered directly)
    # - Modules (introspected for NYAATOOLS_ classes)
    # - Modules/objects with register()/unregister() methods (called automatically)
    items = [
        # 1. PropertyGroups (must be first - operators reference them)
        NyaaAssetMeshEntry,
        NyaaBakeImage,
        NyaaExportProfile,
        NyaaAssetConfig,
        NyaaPropConfig,
        NyaaToolsBakeSettings,
        NyaaToolsExportSettings,
        NyaaToolsSettings,
        # 2. Operators (modules - auto-discover NYAATOOLS_OT_ classes)
        ProgressManager,
        NyaaToolsAddModifier,
        NyaaToolsCheckImageFormats,
        NyaaToolsDissolveBones,
        NyaaToolsHelpImageFormat,
        NyaaToolsImagePacker,
        NyaaToolsMeshCleanup,
        NyaaToolsMergeArmatures,
        NyaaToolsNormalizeArmatureATPose,
        NyaaToolsNormalizeArmatureClearCustomObjects,
        NyaaToolsNormalizeArmatureRename,
        NyaaToolsNormalizeArmatureRetarget,
        NyaaToolsRenamePackedImage,
        NyaaSelectStandardBones,
        PrzemirApplyTopModifier,  # 3rd Party Operator module (contains PrzemirApplyTopModifier class without prefix)
        merge_export_op,
        bake_op,
        LinkButton,
        operators_asset,
        operators_export,
        operators_bake,
        operators_migrate,
        # 3. UI Lists (modules - auto-discover NYAATOOLS_UL_ classes)
        panels_uilists,
        # 4. Panels (modules - auto-discover NYAATOOLS_PT_ classes)
        panels_main,
        panels_utils,
        # 5. Registry modules (auto-register/unregister handlers)
        # Must be called AFTER PropertyGroups are attached (handlers access obj.nyaa_asset).
        asset_registry,
    ]

    # Collect all classes to register (from items list)
    classes_to_register = []
    panel_classes = []  # Collect panels separately to sort by parent dependency
    registry_items = []  # Collect items with register()/unregister() methods
    
    for item in items:
        if inspect.isclass(item):
            # Direct class reference
            classes_to_register.append(item)
        elif inspect.ismodule(item):
            # Check if module has register()/unregister() functions
            has_register = hasattr(item, "register") and callable(item.register)
            has_unregister = hasattr(item, "unregister") and callable(item.unregister)
            
            if has_register and has_unregister:
                # Module with registration functions - add to registry_items
                registry_items.append(item)
            else:
            # Module - introspect for classes
            module_name = item.__name__.split(".")[-1]
            for name, obj in inspect.getmembers(item, inspect.isclass):
                # Include NYAATOOLS_ prefixed classes
                if name.startswith("NYAATOOLS_"):
                    # Separate panels for sorting
                    if name.startswith("NYAATOOLS_PT_"):
                        panel_classes.append(obj)
                    else:
                        classes_to_register.append(obj)
                # Special case: PrzemirApplyTopModifier (3rd party, no prefix)
                elif (
                    module_name == "PrzemirApplyTopModifier"
                    and name == "PrzemirApplyTopModifier"
                ):
                    classes_to_register.append(obj)
        else:
            # Check if object has register()/unregister() methods
            has_register = hasattr(item, "register") and callable(item.register)
            has_unregister = hasattr(item, "unregister") and callable(item.unregister)
            
            if has_register and has_unregister:
                registry_items.append(item)

    # Sort panels: root panels (no bl_parent_id) first, then child panels
    def panel_sort_key(cls):
        has_parent = hasattr(cls, "bl_parent_id") and cls.bl_parent_id
        return (1 if has_parent else 0, cls.__name__)

    panel_classes.sort(key=panel_sort_key)
    classes_to_register.extend(panel_classes)

    if reg:
        # Register all classes
        for cls in classes_to_register:
            bpy.utils.register_class(cls)

        # Attach PropertyGroups to types (after registration)
        bpy.types.Object.nyaa_asset = bpy.props.PointerProperty(type=NyaaAssetConfig)
        bpy.types.Object.nyaa_prop = bpy.props.PointerProperty(type=NyaaPropConfig)
        bpy.types.Scene.nyaa_settings = bpy.props.PointerProperty(
            type=NyaaToolsSettings
        )
        
        # Auto-register items with register() methods (after PropertyGroups are attached)
        for registry_item in registry_items:
            registry_item.register()
    else:
        # Auto-unregister items with unregister() methods (before PropertyGroups are removed)
        for registry_item in reversed(registry_items):
            registry_item.unregister()
        
        # Remove PropertyGroups from types
        for attr_name, type_obj in [
            ("nyaa_settings", bpy.types.Scene),
            ("nyaa_prop", bpy.types.Object),
            ("nyaa_asset", bpy.types.Object),
        ]:
            try:
                delattr(type_obj, attr_name)
            except AttributeError:
                pass

        # Unregister all classes in reverse order
        for cls in reversed(classes_to_register):
            bpy.utils.unregister_class(cls)


def register():
    _toggle_register(True)


def unregister():
    _toggle_register(False)
