import bpy

from .operators.NyaaPanel import NyaaPanel
from .operators.NyaaToolsAddModifier import NyaaToolsAddModifier
from .operators.NyaaToolsAvatarMergeExport import NyaaToolsAvatarMergeExport
from .operators.NyaaToolsBakeMaterialSlots import NyaaToolsBakeMaterialSlots
from .operators.NyaaToolsCheckImageFormats import NyaaToolsCheckImageFormats
from .operators.NyaaToolsConfigureAvatarArmature import NyaaToolsConfigureAvatarArmature
from .operators.NyaaToolsConfigureMeshesOnAvatar import NyaaToolsConfigureMeshesOnAvatar
from .operators.NyaaToolsDissolveBones import NyaaToolsDissolveBones
from .operators.NyaaToolsHelpImageFormat import NyaaToolsHelpImageFormat
from .operators.NyaaToolsImagePacker import NyaaToolsImagePacker
from .operators.NyaaToolsMeshCleanup import NyaaToolsMeshCleanup
from .operators.NyaaToolsMergeArmatures import NyaaToolsMergeArmatures
from .operators.NyaaToolsNormalizeArmatureATPose import NyaaToolsNormalizeArmatureATPose
from .operators.NyaaToolsNormalizeArmatureClearCustomObjects import (
    NyaaToolsNormalizeArmatureClearCustomObjects,
)
from .operators.NyaaToolsNormalizeArmatureRename import NyaaToolsNormalizeArmatureRename
from .operators.NyaaToolsNormalizeArmatureRetarget import (
    NyaaToolsNormalizeArmatureRetarget,
)
from .operators.NyaaToolsRemoveMeshesFromAvatar import NyaaToolsRemoveMeshesFromAvatar
from .operators.NyaaToolsRenamePackedImage import NyaaToolsRenamePackedImage
from .operators.NyaaSelectStandardBones import NyaaSelectStandardBones
from .operators.PrzemirApplyTopModifier import PrzemirApplyTopModifier
from .operators.LinkButton import LinkButton


bl_info = {
    "name": "NyaaTools",
    "author": "Nyaarium",
    "blender": (4, 5, 3),
    "version": (1, 10, 3),
    "description": "Various Nyaarium tools to normalize & fast-export avatars",
    "location": "N-Panel > NyaaTools",
    "category": "Object",
}


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


def register():
    for cls in reversed(classes):
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
