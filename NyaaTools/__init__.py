import bpy

from .operators.NyaaPanel import NyaaPanel
from .operators.NyaaToolsAddModifier import NyaaToolsAddModifier
from .operators.NyaaToolsAvatarMergeExport import NyaaToolsAvatarMergeExport
from .operators.NyaaToolsConfigureAvatarArmature import NyaaToolsConfigureAvatarArmature
from .operators.NyaaToolsConfigureMeshesOnAvatar import NyaaToolsConfigureMeshesOnAvatar
from .operators.NyaaToolsMeshCleanup import NyaaToolsMeshCleanup
from .operators.NyaaToolsNormalizeArmatureATPose import NyaaToolsNormalizeArmatureATPose
from .operators.NyaaToolsRemoveMeshesFromAvatar import NyaaToolsRemoveMeshesFromAvatar
from .operators.NyaaSelectStandardBones import NyaaSelectStandardBones
from .operators.PrzemirApplyTopModifier import PrzemirApplyTopModifier
from .operators.LinkButton import LinkButton


bl_info = {
    "name": "NyaaTools",
    "author": "Nyaarium",
    "blender": (3, 0, 0),
    "version": (1, 3, 2),
    "description": "Various Nyaarium tools to normalize & fast-export avatar FBX's",
    "location": "Tool > NyaaTools",
    "category": "Object",
}


classes = [
    NyaaPanel,
    NyaaToolsAddModifier,
    NyaaToolsAvatarMergeExport,
    NyaaToolsConfigureAvatarArmature,
    NyaaToolsConfigureMeshesOnAvatar,
    NyaaToolsMeshCleanup,
    NyaaToolsNormalizeArmatureATPose,
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
