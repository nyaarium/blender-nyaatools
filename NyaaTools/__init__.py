import bpy

from .operators.NyaaPanel import NyaaPanel
from .operators.NyaaToolsNormalizeArmatureAPose import NyaaToolsNormalizeArmatureAPose
from .operators.NyaaToolsNormalizeArmatureTPose import NyaaToolsNormalizeArmatureTPose
from .operators.NyaaToolsSetArmatureAPose import NyaaToolsSetArmatureAPose
from .operators.NyaaToolsSetArmatureTPose import NyaaToolsSetArmatureTPose
from .operators.NyaaToolsMeshCleanup import NyaaToolsMeshCleanup
from .operators.NyaaToolsAddModifier import NyaaToolsAddModifier
from .operators.NyaaToolsApplyTopModifier import NyaaToolsApplyTopModifier
from .operators.NyaaToolsConfigureAvatarArmature import NyaaToolsConfigureAvatarArmature
from .operators.NyaaToolsConfigureAvatarMesh import NyaaToolsConfigureAvatarMesh
from .operators.NyaaToolsAvatarMergeTool import NyaaToolsAvatarMergeTool
from .operators.LinkButton import LinkButton


bl_info = {
    "name":         "NyaaTools",
    "author":       "Nyaarium",
    "blender":      (3, 0, 0),
    "version":      (1, 1, 1),
    "description":  "Various Nyaarium tools to normalize & export avatar FBX's",
    "location":     "Tool > NyaaTools",
    "category":     "Object",
}


classes = [
    NyaaPanel,
    NyaaToolsNormalizeArmatureAPose,
    NyaaToolsNormalizeArmatureTPose,
    NyaaToolsSetArmatureAPose,
    NyaaToolsSetArmatureTPose,
    NyaaToolsMeshCleanup,
    NyaaToolsAddModifier,
    NyaaToolsApplyTopModifier,
    NyaaToolsConfigureAvatarArmature,
    NyaaToolsConfigureAvatarMesh,
    NyaaToolsAvatarMergeTool,
    LinkButton,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
