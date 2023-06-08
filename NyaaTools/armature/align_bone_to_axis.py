import bpy
from mathutils import Matrix, Vector

from .find_bone import find_bone
from ..bone_desc_map import BONE_DESC_MAP


def align_bone_to_axis(armature, bone, axis_x, axis_y, axis_z):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    def needs_align(bone, axis_x, axis_y, axis_z):
        debug_print("Checking if bone ", bone.name, " needs alignment")
        head = bone.head
        tail = bone.tail

        # Offset axis_x, axis_y, axis_z by head
        target = Vector((head[0] + axis_x, head[1] + axis_y, head[2] + axis_z))

        # Vector from head to tail
        tv = target - head
        bv = tail - head
        rot = tv.rotation_difference(bv)

        # If bone rotation is already aligned, return False
        if rot.angle == 0:
            debug_print("Bone ", bone.name, " is already aligned")
            return False

        # If the bone is not aligned, return True
        debug_print("Bone ", bone.name, " is not aligned")
        return True

    def _helper_align(bone, axis_x, axis_y, axis_z):
        # Set target to be 1 meter in an axis direction away from head
        head = bone.head
        tail = bone.tail

        # Offset axis_x, axis_y, axis_z by head
        target = Vector((head[0] + axis_x, head[1] + axis_y, head[2] + axis_z))

        # Vector from head to tail
        tv = target - head
        bv = tail - head

        # Quaternion that rotates bv to v
        rd = bv.rotation_difference(tv)
        debug_print("Rotating bone ", bone.name, " by ", rd.angle)

        # Matrix that rotates bone to v
        M = (
            Matrix.Translation(head) @
            rd.to_matrix().to_4x4() @
            Matrix.Translation(-head)
        )

        bone.matrix = M @ bone.matrix

    def set_mode():
        if isinstance(bone, bpy.types.EditBone):
            bpy.ops.object.mode_set(mode="EDIT")
        else:
            bpy.ops.object.mode_set(mode="POSE")

    # type check
    if bone == None:
        raise TypeError("Bone was not found")

    if not isinstance(bone, bpy.types.EditBone) and not isinstance(bone, bpy.types.PoseBone):
        raise TypeError("Bone must be a EditBone or PoseBone")

    if isinstance(bone, bpy.types.EditBone):
        debug_print("Aligning bone ", bone.name, " (EditBone)")
    else:
        debug_print("Aligning bone ", bone.name, " (PoseBone)")

    set_mode()

    alignment_changed = False

    # If bone ends in .L or .R, apply it on the mirrored bone as well
    if bone.name.endswith(".L") or bone.name.endswith(".R"):
        # Run on bone
        if needs_align(bone, axis_x, axis_y, axis_z):
            _helper_align(bone, axis_x, axis_y, axis_z)
            alignment_changed = True

        # And then the mirrored bone
        mirrored_bone_name = BONE_DESC_MAP[bone.name]["mirror"]
        debug_print("Mirrored bone name: ", mirrored_bone_name)

        if isinstance(bone, bpy.types.EditBone):
            mirrored_bone = find_bone("edit", armature, mirrored_bone_name)
        else:
            mirrored_bone = find_bone("pose", armature, mirrored_bone_name)

        set_mode()

        if mirrored_bone != None:
            debug_print("Mirrored bone found: ", mirrored_bone_name)

            # Run on mirrored bone
            if needs_align(mirrored_bone, -axis_x, axis_y, axis_z):
                _helper_align(mirrored_bone, -axis_x, axis_y, axis_z)
                alignment_changed = True
    else:
        # Run it as requested
        if needs_align(bone, axis_x, axis_y, axis_z):
            _helper_align(bone, axis_x, axis_y, axis_z)
            alignment_changed = True

    return alignment_changed
