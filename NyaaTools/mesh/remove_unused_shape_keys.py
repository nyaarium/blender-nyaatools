import bpy
import numpy
from ..consts import SHAPE_KEY_TOLERANCE


def remove_unused_shape_keys(obj):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    if obj.type == None:
        raise BaseException("Expected a mesh object, got: None")
    if obj.type != "MESH":
        raise BaseException("Expected a mesh object, got: " + obj.type)
    if not obj.data.shape_keys:
        debug_print("No shape keys. Skipping", obj.name)
        return
    if not obj.data.shape_keys.use_relative:
        debug_print("Shape keys not using relative mode. Skipping", obj.name)
        return

    # Get all the key blocks (shape keys) for the mesh
    kbs = obj.data.shape_keys.key_blocks
    nverts = len(obj.data.vertices)
    to_delete = []
    cache = {}

    # Create an array to store the vertex locations
    locs = numpy.empty(3 * nverts, dtype=numpy.float32)

    # Loop through all the shape keys for the mesh
    for kb in kbs:
        # Skip self
        if kb == kb.relative_key:
            continue

        # Get the vertex locations for this shape key
        kb.data.foreach_get("co", locs)

        # If we haven't already cached the relative key for this shape key,
        # get the vertex locations for the relative key and cache them
        if kb.relative_key.name not in cache:
            rel_locs = numpy.empty(3 * nverts, dtype=numpy.float32)
            kb.relative_key.data.foreach_get("co", rel_locs)
            cache[kb.relative_key.name] = rel_locs

        # Get the cached relative key vertex locations
        rel_locs = cache[kb.relative_key.name]

        # Calculate the largest distance between the relative key and the shape key
        distances = numpy.abs(locs - rel_locs)
        largestDistance = numpy.amax(distances)

        # Print the largest distance
        # debug_print("Largest distance for", kb.name, "is", largestDistance)

        # Check if all the vertex locations are within the tolerance
        if (distances < SHAPE_KEY_TOLERANCE).all():
            # If so, add this shape key to the list to delete
            # Only if it's not a Face VRC* kb though.
            if not is_vrc_face_workaround(obj, kb.name):
                to_delete.append(kb.name)

    # Loop through all the shape keys to delete and remove them from the mesh
    for kb_name in to_delete:
        debug_print("Removing shape key: ", obj.name, " -> ", kb_name)
        obj.shape_key_remove(obj.data.shape_keys.key_blocks[kb_name])

    if len(obj.data.shape_keys.key_blocks) == 1:
        kb = obj.data.shape_keys.key_blocks[0]
        debug_print("Removing shape key: ", obj.name, " -> ", kb.name)
        obj.shape_key_remove(kb)


# HACK: This is a VRChat workaround. Reimplement better later.
def is_vrc_face_workaround(obj, key_name):
    key_name = key_name.lower()

    if key_name.startswith("vrc.") or key_name.startswith("v_"):
        if obj.name.lower() == "face" or obj.name.lower() == "head":
            return True

        elif obj.name.lower() == "body":
            # If "Body", but there is no mesh in the scene named "Face" or "Head"
            for obj in bpy.data.objects:
                if obj.type == "MESH":
                    if obj.name.lower() == "face" or obj.name.lower() == "head":
                        return False
            return True

    return False
