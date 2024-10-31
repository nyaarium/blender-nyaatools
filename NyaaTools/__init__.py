import bpy

from .operators.NyaaPanel import NyaaPanel
from .operators.NyaaToolsAddModifier import NyaaToolsAddModifier
from .operators.NyaaToolsAvatarMergeExport import NyaaToolsAvatarMergeExport
from .operators.NyaaToolsConfigureAvatarArmature import NyaaToolsConfigureAvatarArmature
from .operators.NyaaToolsConfigureMeshesOnAvatar import NyaaToolsConfigureMeshesOnAvatar
from .operators.NyaaToolsDissolveBones import NyaaToolsDissolveBones
from .operators.NyaaToolsMeshCleanup import NyaaToolsMeshCleanup
from .operators.NyaaToolsMergeArmatures import NyaaToolsMergeArmatures
from .operators.NyaaToolsNormalizeArmatureATPose import NyaaToolsNormalizeArmatureATPose
from .operators.NyaaToolsNormalizeArmatureRename import NyaaToolsNormalizeArmatureRename
from .operators.NyaaToolsNormalizeArmatureRetarget import NyaaToolsNormalizeArmatureRetarget
from .operators.NyaaToolsRemoveMeshesFromAvatar import NyaaToolsRemoveMeshesFromAvatar
from .operators.NyaaSelectStandardBones import NyaaSelectStandardBones
from .operators.PrzemirApplyTopModifier import PrzemirApplyTopModifier
from .operators.LinkButton import LinkButton


bl_info = {
    "name": "NyaaTools",
    "author": "Nyaarium",
    "blender": (4, 0, 0),
    "version": (1, 7, 3),
    "description": "Various Nyaarium tools to normalize & fast-export avatar FBX's",
    "location": "N-Panel > NyaaTools",
    "category": "Object",
}


classes = [
    NyaaPanel,
    NyaaToolsAddModifier,
    NyaaToolsAvatarMergeExport,
    NyaaToolsConfigureAvatarArmature,
    NyaaToolsConfigureMeshesOnAvatar,
    NyaaToolsDissolveBones,
    NyaaToolsMeshCleanup,
    NyaaToolsMergeArmatures,
    NyaaToolsNormalizeArmatureATPose,
    NyaaToolsNormalizeArmatureRename,
    NyaaToolsNormalizeArmatureRetarget,
    NyaaToolsRemoveMeshesFromAvatar,
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
