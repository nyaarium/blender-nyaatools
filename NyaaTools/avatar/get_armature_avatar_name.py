import bpy
from NyaaTools.common.get_prop import get_prop
from ..consts import PROP_AVATAR_EXPORT_PATH, PROP_AVATAR_LAYERS, PROP_AVATAR_NAME


def get_armature_avatar_name(armature):
	return get_prop(armature, PROP_AVATAR_NAME)
