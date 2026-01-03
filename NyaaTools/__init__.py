import bpy

from . import dev_reload


bl_info = {
    "name": "NyaaTools",
    "author": "Nyaarium",
    "blender": (4, 5, 3),
    "version": (1, 10, 5),
    "description": "Various Nyaarium tools to normalize & fast-export avatars",
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
    from .operators.NyaaPanel import NyaaPanel
    from .operators.NyaaToolsAddModifier import NyaaToolsAddModifier
    from .operators.NyaaToolsAvatarMergeExport import NyaaToolsAvatarMergeExport
    from .operators.NyaaToolsBakeMaterialSlots import NyaaToolsBakeMaterialSlots
    from .operators.NyaaToolsCheckImageFormats import NyaaToolsCheckImageFormats
    from .operators.NyaaToolsConfigureAvatarArmature import (
        NyaaToolsConfigureAvatarArmature,
    )
    from .operators.NyaaToolsConfigureMeshesOnAvatar import (
        NyaaToolsConfigureMeshesOnAvatar,
    )
    from .operators.NyaaToolsDissolveBones import NyaaToolsDissolveBones
    from .operators.NyaaToolsHelpImageFormat import NyaaToolsHelpImageFormat
    from .operators.NyaaToolsImagePacker import NyaaToolsImagePacker
    from .operators.NyaaToolsMeshCleanup import NyaaToolsMeshCleanup
    from .operators.NyaaToolsMergeArmatures import NyaaToolsMergeArmatures
    from .operators.NyaaToolsNormalizeArmatureATPose import (
        NyaaToolsNormalizeArmatureATPose,
    )
    from .operators.NyaaToolsNormalizeArmatureClearCustomObjects import (
        NyaaToolsNormalizeArmatureClearCustomObjects,
    )
    from .operators.NyaaToolsNormalizeArmatureRename import (
        NyaaToolsNormalizeArmatureRename,
    )
    from .operators.NyaaToolsNormalizeArmatureRetarget import (
        NyaaToolsNormalizeArmatureRetarget,
    )
    from .operators.NyaaToolsRemoveMeshesFromAvatar import (
        NyaaToolsRemoveMeshesFromAvatar,
    )
    from .operators.NyaaToolsRenamePackedImage import (
        NyaaToolsRenamePackedImage,
    )
    from .operators.NyaaSelectStandardBones import NyaaSelectStandardBones
    from .operators.PrzemirApplyTopModifier import PrzemirApplyTopModifier
    from .operators.LinkButton import LinkButton

    # Build class list from freshly imported modules
    classes = [
        NyaaPanel,
        NyaaToolsAddModifier,
        NyaaToolsAvatarMergeExport,
        NyaaToolsBakeMaterialSlots,
        NyaaToolsCheckImageFormats,
        NyaaToolsConfigureAvatarArmature,
        NyaaToolsConfigureMeshesOnAvatar,
        NyaaToolsDissolveBones,
        NyaaToolsHelpImageFormat,
        NyaaToolsImagePacker,
        NyaaToolsMeshCleanup,
        NyaaToolsMergeArmatures,
        NyaaToolsNormalizeArmatureATPose,
        NyaaToolsNormalizeArmatureClearCustomObjects,
        NyaaToolsNormalizeArmatureRename,
        NyaaToolsNormalizeArmatureRetarget,
        NyaaToolsRemoveMeshesFromAvatar,
        NyaaToolsRenamePackedImage,
        NyaaSelectStandardBones,
        PrzemirApplyTopModifier,
        LinkButton,
    ]

    for cls in reversed(classes):
        bpy.utils.register_class(cls)


def unregister():
    # Import modules (use current cached versions)
    from .operators.NyaaPanel import NyaaPanel
    from .operators.NyaaToolsAddModifier import NyaaToolsAddModifier
    from .operators.NyaaToolsAvatarMergeExport import NyaaToolsAvatarMergeExport
    from .operators.NyaaToolsBakeMaterialSlots import NyaaToolsBakeMaterialSlots
    from .operators.NyaaToolsCheckImageFormats import NyaaToolsCheckImageFormats
    from .operators.NyaaToolsConfigureAvatarArmature import (
        NyaaToolsConfigureAvatarArmature,
    )
    from .operators.NyaaToolsConfigureMeshesOnAvatar import (
        NyaaToolsConfigureMeshesOnAvatar,
    )
    from .operators.NyaaToolsDissolveBones import NyaaToolsDissolveBones
    from .operators.NyaaToolsHelpImageFormat import NyaaToolsHelpImageFormat
    from .operators.NyaaToolsImagePacker import NyaaToolsImagePacker
    from .operators.NyaaToolsMeshCleanup import NyaaToolsMeshCleanup
    from .operators.NyaaToolsMergeArmatures import NyaaToolsMergeArmatures
    from .operators.NyaaToolsNormalizeArmatureATPose import (
        NyaaToolsNormalizeArmatureATPose,
    )
    from .operators.NyaaToolsNormalizeArmatureClearCustomObjects import (
        NyaaToolsNormalizeArmatureClearCustomObjects,
    )
    from .operators.NyaaToolsNormalizeArmatureRename import (
        NyaaToolsNormalizeArmatureRename,
    )
    from .operators.NyaaToolsNormalizeArmatureRetarget import (
        NyaaToolsNormalizeArmatureRetarget,
    )
    from .operators.NyaaToolsRemoveMeshesFromAvatar import (
        NyaaToolsRemoveMeshesFromAvatar,
    )
    from .operators.NyaaToolsRenamePackedImage import (
        NyaaToolsRenamePackedImage,
    )
    from .operators.NyaaSelectStandardBones import NyaaSelectStandardBones
    from .operators.PrzemirApplyTopModifier import PrzemirApplyTopModifier
    from .operators.LinkButton import LinkButton

    # Build class list
    classes = [
        NyaaPanel,
        NyaaToolsAddModifier,
        NyaaToolsAvatarMergeExport,
        NyaaToolsBakeMaterialSlots,
        NyaaToolsCheckImageFormats,
        NyaaToolsConfigureAvatarArmature,
        NyaaToolsConfigureMeshesOnAvatar,
        NyaaToolsDissolveBones,
        NyaaToolsHelpImageFormat,
        NyaaToolsImagePacker,
        NyaaToolsMeshCleanup,
        NyaaToolsMergeArmatures,
        NyaaToolsNormalizeArmatureATPose,
        NyaaToolsNormalizeArmatureClearCustomObjects,
        NyaaToolsNormalizeArmatureRename,
        NyaaToolsNormalizeArmatureRetarget,
        NyaaToolsRemoveMeshesFromAvatar,
        NyaaToolsRenamePackedImage,
        NyaaSelectStandardBones,
        PrzemirApplyTopModifier,
        LinkButton,
    ]

    for cls in classes:
        bpy.utils.unregister_class(cls)
