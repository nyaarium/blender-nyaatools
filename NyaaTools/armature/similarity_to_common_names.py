from ..common.string_similarity import string_similarity
from ..bone_desc_map import BONE_DESC_MAP


def similarity_to_common_names(bone_name: str, bone_desc_name: str) -> float:
    if not isinstance(bone_desc_name, str):
        raise TypeError("bone_desc_name must be type str")

    common_names = BONE_DESC_MAP[bone_desc_name]["common_names"]
    if common_names:
        # Return largest string_similarity value
        return max(
            string_similarity(bone_name, common_name) for common_name in common_names
        )
    else:
        return string_similarity(bone_name, bone_desc_name)
