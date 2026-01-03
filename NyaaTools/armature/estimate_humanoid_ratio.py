"""
Estimate how humanoid an armature is based on bone matching.

Returns a ratio (0.0 to 1.0) of how many standard humanoid bones are present.
Used to determine if an asset should show normalization tools.
"""

from ..bone_desc_map import BONE_DESC_MAP
from ..armature.similarity_to_common_names import similarity_to_common_names


# Core humanoid bones that must be present (non-optional)
CORE_HUMANOID_BONES = [
    "Hips",
    "Spine",
    "Chest",
    "Neck",
    "Head",
    "Shoulder.L",
    "Shoulder.R",
    "Upper Arm.L",
    "Upper Arm.R",
    "Lower Arm.L",
    "Lower Arm.R",
    "Hand.L",
    "Hand.R",
    "Upper Leg.L",
    "Upper Leg.R",
    "Lower Leg.L",
    "Lower Leg.R",
    "Foot.L",
    "Foot.R",
]


def estimate_humanoid_ratio(armature_obj) -> float:
    """
    Estimate how humanoid an armature is.
    
    Args:
        armature_obj: A Blender armature object
        
    Returns:
        A float from 0.0 to 1.0 indicating humanoid similarity.
        0.8+ is considered a humanoid avatar.
    """
    if armature_obj is None or armature_obj.type != "ARMATURE":
        return 0.0
    
    armature = armature_obj.data
    if not armature.bones:
        return 0.0
    
    bone_names = [bone.name for bone in armature.bones]
    
    matched = 0
    total = len(CORE_HUMANOID_BONES)
    
    for desc_name in CORE_HUMANOID_BONES:
        if desc_name not in BONE_DESC_MAP:
            continue
            
        # Find the best matching bone in the armature
        best_similarity = 0.0
        for bone_name in bone_names:
            similarity = similarity_to_common_names(bone_name, desc_name)
            if similarity > best_similarity:
                best_similarity = similarity
        
        # Consider a bone matched if similarity is high enough
        if best_similarity >= 0.7:
            matched += 1
    
    return matched / total if total > 0 else 0.0


def is_humanoid(armature_obj, threshold: float = 0.8) -> bool:
    """
    Check if an armature is likely a humanoid.
    
    Args:
        armature_obj: A Blender armature object
        threshold: Minimum ratio to be considered humanoid (default 0.8 = 80%)
        
    Returns:
        True if the armature matches at least threshold% of humanoid bones.
    """
    return estimate_humanoid_ratio(armature_obj) >= threshold
