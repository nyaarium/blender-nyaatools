import bpy

from . import dev_reload


bl_info = {
    "name": "NyaaTools",
    "author": "Nyaarium",
    "blender": (5, 0, 1),
    "version": (2, 1, 0),
    "description": "Various Nyaarium tools for mesh cleanup, merging, and exporting assets",
    "location": "N-Panel > NyaaTools",
    "category": "Object",
}


# Track if we've registered before (for hot reload)
_has_registered = False


def register():
    global _has_registered

    # Hot reload: if re-enabling addon, reload all submodules from disk first
    if _has_registered:
        dev_reload.reload_submodules()
    _has_registered = True

    # Import modules fresh (after potential reload)
    from . import types
    from .ui import eta_estimator
    from .operators import NyaaToolsAddModifier
    from .operators import NyaaToolsAssetMergeExport
    from .operators import NyaaToolsBakeMaterialSlots
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
    from .panels import LinkButton, NyaaPanel

    # Register PropertyGroups first (operators may reference them)
    types.register()

    # Register UI module (ETA estimator has scene properties)
    eta_estimator.register()

    # Build class list from freshly imported modules
    classes = [
        NyaaToolsAddModifier.NyaaToolsAddModifier,
        NyaaToolsAssetMergeExport.NyaaToolsAssetMergeExport,
        NyaaToolsBakeMaterialSlots.NyaaToolsBakeMaterialSlots,
        NyaaToolsCheckImageFormats.NyaaToolsCheckImageFormats,
        NyaaToolsDissolveBones.NyaaToolsDissolveBones,
        NyaaToolsHelpImageFormat.NyaaToolsHelpImageFormat,
        NyaaToolsImagePacker.NyaaToolsImagePacker,
        NyaaToolsMeshCleanup.NyaaToolsMeshCleanup,
        NyaaToolsMergeArmatures.NyaaToolsMergeArmatures,
        NyaaToolsNormalizeArmatureATPose.NyaaToolsNormalizeArmatureATPose,
        NyaaToolsNormalizeArmatureClearCustomObjects.NyaaToolsNormalizeArmatureClearCustomObjects,
        NyaaToolsNormalizeArmatureRename.NyaaToolsNormalizeArmatureRename,
        NyaaToolsNormalizeArmatureRetarget.NyaaToolsNormalizeArmatureRetarget,
        NyaaToolsRenamePackedImage.NyaaToolsRenamePackedImage,
        NyaaSelectStandardBones.NyaaSelectStandardBones,
        PrzemirApplyTopModifier.PrzemirApplyTopModifier,
        LinkButton.LinkButton,
    ]

    for cls in reversed(classes):
        bpy.utils.register_class(cls)

    # Register panel (has its own internal class list)
    NyaaPanel.register()


def unregister():
    # Import modules (use current cached versions)
    from . import types
    from .ui import eta_estimator
    from .operators import NyaaToolsAddModifier
    from .operators import NyaaToolsAssetMergeExport
    from .operators import NyaaToolsBakeMaterialSlots
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
    from .panels import LinkButton, NyaaPanel

    # Unregister panel first
    NyaaPanel.unregister()

    # Build class list
    classes = [
        NyaaToolsAddModifier.NyaaToolsAddModifier,
        NyaaToolsAssetMergeExport.NyaaToolsAssetMergeExport,
        NyaaToolsBakeMaterialSlots.NyaaToolsBakeMaterialSlots,
        NyaaToolsCheckImageFormats.NyaaToolsCheckImageFormats,
        NyaaToolsDissolveBones.NyaaToolsDissolveBones,
        NyaaToolsHelpImageFormat.NyaaToolsHelpImageFormat,
        NyaaToolsImagePacker.NyaaToolsImagePacker,
        NyaaToolsMeshCleanup.NyaaToolsMeshCleanup,
        NyaaToolsMergeArmatures.NyaaToolsMergeArmatures,
        NyaaToolsNormalizeArmatureATPose.NyaaToolsNormalizeArmatureATPose,
        NyaaToolsNormalizeArmatureClearCustomObjects.NyaaToolsNormalizeArmatureClearCustomObjects,
        NyaaToolsNormalizeArmatureRename.NyaaToolsNormalizeArmatureRename,
        NyaaToolsNormalizeArmatureRetarget.NyaaToolsNormalizeArmatureRetarget,
        NyaaToolsRenamePackedImage.NyaaToolsRenamePackedImage,
        NyaaSelectStandardBones.NyaaSelectStandardBones,
        PrzemirApplyTopModifier.PrzemirApplyTopModifier,
        LinkButton.LinkButton,
    ]

    for cls in classes:
        bpy.utils.unregister_class(cls)

    # Unregister UI module
    eta_estimator.unregister()

    # Unregister PropertyGroups last (operators may reference them)
    types.unregister()
