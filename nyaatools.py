from bpy.utils import register_class
from bpy.types import Operator, Panel
from bpy.props import *
from mathutils import Matrix, Vector
import numpy as np
from collections import defaultdict
from typing import Optional
import webbrowser
import traceback
import time
import re
import math
import bpy


bl_info = {
    "name":         "NyaaTools",
    "author":       "Nyaarium, (and lots of StackOverflow). Uses Przemysław Bągard's Apply modifier",
    "blender":      (3, 5, 1),
    "version":      (1, 0, 0),
    "description":  "Various Nyaarium tools to normalize & export avatar FBX's",
    "location":     "TBD",
    "category":     "TBD"
}


# ctx = bpy.context.copy()


#############################################
# Prop Key Constants

VERSION = "1.0.0"
EXPORT_COLLECTION = "Export"
PROP_AVATAR = "avatar"
PROP_TARGET_AVATARS = "targetAvatars"
PROP_EXPORT_PATH = "exportPath"

# Prop Key Constants
#############################################


# This bone description map is used to
BONE_DESC_MAP = {
    # Bone Descriptions
    # common_names: Use "." instead of "_" for improved search results

    "Hips": {
        "common_names": ["Hips", "Hip", "Pelvis"],
        "parent": None,
        "children": ["Spine", "Thigh.L", "Thigh.R"],
        "mirror": None,
    },
    "Spine": {
        "common_names": ["Spine"],
        "parent": "Hips",
        "children": ["Chest"],
        "mirror": None,
        "connected": True,
    },
    "Chest": {
        "common_names": ["Chest", "Breast Root", "Shoulder.L", "Shoulder.R"],
        "parent": "Spine",
        "children": ["Neck", "Breast Root"],
        "mirror": None,
        "connected": True,
    },
    "Neck": {
        "common_names": ["Neck"],
        "parent": "Chest",
        "children": ["Head"],
        "mirror": None,
    },
    "Head": {
        "common_names": ["Head"],
        "parent": "Neck",
        "children": ["Eye.L", "Eye.R"],
        "mirror": None,
        "connected": True,
    },
    "Eye.L": {
        "common_names": ["Eye.L", "Left Eye"],
        "parent": "Head",
        "children": None,
        "mirror": "Eye.R",
        "roll": 90,
    },
    "Eye.R": {
        "common_names": ["Eye.R", "Right Eye"],
        "parent": "Head",
        "children": None,
        "mirror": "Eye.L",
        "roll": 90,
    },

    "Breast Root": {
        "common_names": ["Breast Root", "Boob Root"],
        "parent": "Chest",
        "children": ["Breast.R", "Breast.L"],
        "mirror": None,
    },
    "Breast.L": {
        "common_names": ["Breast", "BreastUpper2_L", "Left Breast"],
        "parent": "Breast Root",
        "children": None,
        "mirror": "Breast.R",
    },
    "Breast.R": {
        "common_names": ["Breast", "BreastUpper2_R", "Right Breast"],
        "parent": "Breast Root",
        "children": None,
        "mirror": "Breast.L",
    },

    "Thigh.L": {
        "common_names": ["Thigh.L", "Leg.L", "Upper Leg.L", "Left Leg"],
        "parent": "Hips",
        "children": ["Knee.L"],
        "mirror": "Thigh.R",
        "roll": 180,
    },
    "Knee.L": {
        "common_names": ["Knee.L", "Lower Leg.L", "Left Knee"],
        "parent": "Thigh.L",
        "children": ["Ankle.L"],
        "mirror": "Knee.R",
        "connected": True,
        "roll": 180,
    },
    "Ankle.L": {
        "common_names": ["Ankle.L", "Foot.L", "Left Ankle", "Left Foot"],
        "parent": "Knee.L",
        "children": ["Toe.L"],
        "mirror": "Ankle.R",
        "connected": True,
    },
    "Toe.L": {
        "common_names": ["Toe.L", "Left Toe"],
        "parent": "Ankle.L",
        "children": None,
        "mirror": "Toe.R",
    },

    "Thigh.R": {
        "common_names": ["Thigh.R", "Leg.R", "Upper Leg.R", "Right Leg"],
        "parent": "Hips",
        "children": ["Knee.R"],
        "mirror": "Thigh.L",
        "roll": 180,
    },
    "Knee.R": {
        "common_names": ["Knee.R", "Lower Leg.R", "Right Knee"],
        "parent": "Thigh.R",
        "children": ["Ankle.R"],
        "mirror": "Knee.L",
        "connected": True,
        "roll": 180,
    },
    "Ankle.R": {
        "common_names": ["Ankle.R", "Foot.R", "Right Ankle", "Right Foot"],
        "parent": "Knee.R",
        "children": ["Toe.R"],
        "mirror": "Ankle.L",
        "connected": True,
    },
    "Toe.R": {
        "common_names": ["Toe.R", "Right Toe"],
        "parent": "Ankle.R",
        "children": None,
        "mirror": "Toe.L",
    },

    "Shoulder.L": {
        "common_names": ["Shoulder.L", "Left Shoulder"],
        "parent": "Chest",
        "children": ["Arm.L"],
        "mirror": "Shoulder.R",
        "roll": 0,
    },
    "Arm.L": {
        "common_names": ["Arm.L", "Upper Arm.L", "Left Arm"],
        "parent": "Shoulder.L",
        "children": ["Elbow.L"],
        "mirror": "Arm.R",
        "connected": True,
        "roll": 60,
    },
    "Elbow.L": {
        "common_names": ["Elbow.L", "Left Elbow", "Lower Arm.L"],
        "parent": "Arm.L",
        "children": ["Wrist.L"],
        "mirror": "Elbow.R",
        "connected": True,
        "roll": 0,
    },
    "Wrist.L": {
        "common_names": ["Wrist.L", "Left Wrist", "Hand.L"],
        "parent": "Elbow.L",
        "children": ["Thumb 1.L", "Little Finger 1.L", "Ring Finger 1.L", "Middle Finger 1.L", "Index Finger 1.L"],
        "mirror": "Wrist.R",
        "connected": True,
        "roll": 0,
    },

    "Shoulder.R": {
        "common_names": ["Shoulder.R", "Right Shoulder"],
        "parent": "Chest",
        "children": ["Arm.R"],
        "mirror": "Shoulder.L",
        "roll": -0,
    },
    "Arm.R": {
        "common_names": ["Arm.R", "Upper Arm.R", "Right Arm"],
        "parent": "Shoulder.R",
        "children": ["Elbow.R"],
        "mirror": "Arm.L",
        "connected": True,
        "roll": -90,
    },
    "Elbow.R": {
        "common_names": ["Elbow.R", "Right Elbow", "Lower Arm.R"],
        "parent": "Arm.R",
        "children": ["Wrist.R"],
        "mirror": "Elbow.L",
        "connected": True,
        "roll": -0,
    },
    "Wrist.R": {
        "common_names": ["Wrist.R", "Right Wrist", "Hand.R"],
        "parent": "Elbow.R",
        "children": ["Thumb 1.R", "Little Finger 1.R", "Ring Finger 1.R", "Middle Finger 1.R", "Index Finger 1.R"],
        "mirror": "Wrist.L",
        "connected": True,
        "roll": -0,
    },

    "Thumb 1.L": {
        "common_names": ["Thumb0.L"],
        "parent": "Wrist.L",
        "children": ["Thumb 2.L"],
        "mirror": "Thumb 1.R",
        "roll": 0,
    },
    "Thumb 2.L": {
        "common_names": ["Thumb1.L"],
        "parent": "Thumb 1.L",
        "children": ["Thumb 3.L"],
        "mirror": "Thumb 2.R",
        "connected": True,
        "roll": 0,
    },
    "Thumb 3.L": {
        "common_names": ["Thumb2.L"],
        "parent": "Thumb 2.L",
        "children": None,
        "mirror": "Thumb 3.R",
        "connected": True,
        "roll": 0,
    },
    "Index Finger 1.L": {
        "common_names": ["IndexFinger1.L"],
        "parent": "Wrist.L",
        "children": ["Index Finger 2.L"],
        "mirror": "Index Finger 1.R",
        "roll": 0,
    },
    "Index Finger 2.L": {
        "common_names": ["IndexFinger2.L"],
        "parent": "Index Finger 1.L",
        "children": ["Index Finger 3.L"],
        "mirror": "Index Finger 2.R",
        "connected": True,
        "roll": 0,
    },
    "Index Finger 3.L": {
        "common_names": ["IndexFinger3.L"],
        "parent": "Index Finger 2.L",
        "children": None,
        "mirror": "Index Finger 3.R",
        "connected": True,
        "roll": 0,
    },
    "Middle Finger 1.L": {
        "common_names": ["MiddleFinger1.L"],
        "parent": "Wrist.L",
        "children": ["Middle Finger 2.L"],
        "mirror": "Middle Finger 1.R",
        "roll": 0,
    },
    "Middle Finger 2.L": {
        "common_names": ["MiddleFinger2.L"],
        "parent": "Middle Finger 1.L",
        "children": ["Middle Finger 3.L"],
        "mirror": "Middle Finger 2.R",
        "connected": True,
        "roll": 0,
    },
    "Middle Finger 3.L": {
        "common_names": ["MiddleFinger3.L"],
        "parent": "Middle Finger 2.L",
        "children": None,
        "mirror": "Middle Finger 3.R",
        "connected": True,
        "roll": 0,
    },
    "Ring Finger 1.L": {
        "common_names": ["RingFinger1.L"],
        "parent": "Wrist.L",
        "children": ["Ring Finger 2.L"],
        "mirror": "Ring Finger 1.R",
        "roll": 0,
    },
    "Ring Finger 2.L": {
        "common_names": ["RingFinger2.L"],
        "parent": "Ring Finger 1.L",
        "children": ["Ring Finger 3.L"],
        "mirror": "Ring Finger 2.R",
        "connected": True,
        "roll": 0,
    },
    "Ring Finger 3.L": {
        "common_names": ["RingFinger3.L"],
        "parent": "Ring Finger 2.L",
        "children": None,
        "mirror": "Ring Finger 3.R",
        "connected": True,
        "roll": 0,
    },
    "Little Finger 1.L": {
        "common_names": ["LittleFinger1.L"],
        "parent": "Wrist.L",
        "children": ["Little Finger 2.L"],
        "mirror": "Little Finger 1.R",
        "roll": 0,
    },
    "Little Finger 2.L": {
        "common_names": ["LittleFinger2.L"],
        "parent": "Little Finger 1.L",
        "children": ["Little Finger 3.L"],
        "mirror": "Little Finger 2.R",
        "connected": True,
        "roll": 0,
    },
    "Little Finger 3.L": {
        "common_names": ["LittleFinger3.L"],
        "parent": "Little Finger 2.L",
        "children": None,
        "mirror": "Little Finger 3.R",
        "connected": True,
        "roll": 0,
    },

    "Thumb 1.R": {
        "common_names": ["Thumb0.R"],
        "parent": "Wrist.R",
        "children": ["Thumb 2.R"],
        "mirror": "Thumb 1.L",
        "roll": -0,
    },
    "Thumb 2.R": {
        "common_names": ["Thumb1.R"],
        "parent": "Thumb 1.R",
        "children": ["Thumb 3.R"],
        "mirror": "Thumb 2.L",
        "connected": True,
        "roll": -0,
    },
    "Thumb 3.R": {
        "common_names": ["Thumb2.R"],
        "parent": "Thumb 2.R",
        "children": None,
        "mirror": "Thumb 3.L",
        "connected": True,
        "roll": -0,
    },
    "Index Finger 1.R": {
        "common_names": ["IndexFinger1.R"],
        "parent": "Wrist.R",
        "children": ["Index Finger 2.R"],
        "mirror": "Index Finger 1.L",
        "roll": -0,
    },
    "Index Finger 2.R": {
        "common_names": ["IndexFinger2.R"],
        "parent": "Index Finger 1.R",
        "children": ["Index Finger 3.R"],
        "mirror": "Index Finger 2.L",
        "connected": True,
        "roll": -0,
    },
    "Index Finger 3.R": {
        "common_names": ["IndexFinger3.R"],
        "parent": "Index Finger 2.R",
        "children": None,
        "mirror": "Index Finger 3.L",
        "connected": True,
        "roll": -0,
    },
    "Middle Finger 1.R": {
        "common_names": ["MiddleFinger1.R"],
        "parent": "Wrist.R",
        "children": ["Middle Finger 2.R"],
        "mirror": "Middle Finger 1.L",
        "roll": -0,
    },
    "Middle Finger 2.R": {
        "common_names": ["MiddleFinger2.R"],
        "parent": "Middle Finger 1.R",
        "children": ["Middle Finger 3.R"],
        "mirror": "Middle Finger 2.L",
        "connected": True,
        "roll": -0,
    },
    "Middle Finger 3.R": {
        "common_names": ["MiddleFinger3.R"],
        "parent": "Middle Finger 2.R",
        "children": None,
        "mirror": "Middle Finger 3.L",
        "connected": True,
        "roll": -0,
    },
    "Ring Finger 1.R": {
        "common_names": ["RingFinger1.R"],
        "parent": "Wrist.R",
        "children": ["Ring Finger 2.R"],
        "mirror": "Ring Finger 1.L",
        "roll": -0,
    },
    "Ring Finger 2.R": {
        "common_names": ["RingFinger2.R"],
        "parent": "Ring Finger 1.R",
        "children": ["Ring Finger 3.R"],
        "mirror": "Ring Finger 2.L",
        "connected": True,
        "roll": -0,
    },
    "Ring Finger 3.R": {
        "common_names": ["RingFinger3.R"],
        "parent": "Ring Finger 2.R",
        "children": None,
        "mirror": "Ring Finger 3.L",
        "connected": True,
        "roll": -0,
    },
    "Little Finger 1.R": {
        "common_names": ["LittleFinger1.R"],
        "parent": "Wrist.R",
        "children": ["Little Finger 2.R"],
        "mirror": "Little Finger 1.L",
        "roll": -0,
    },
    "Little Finger 2.R": {
        "common_names": ["LittleFinger2.R"],
        "parent": "Little Finger 1.R",
        "children": ["Little Finger 3.R"],
        "mirror": "Little Finger 2.L",
        "connected": True,
        "roll": -0,
    },
    "Little Finger 3.R": {
        "common_names": ["LittleFinger3.R"],
        "parent": "Little Finger 2.R",
        "children": None,
        "mirror": "Little Finger 3.L",
        "connected": True,
        "roll": -0,
    },
}


def cleanupMesh(obj):
    if (obj == None):
        raise BaseException(
            "cleanupMesh() :: Expected a mesh object, got: None")
    if (obj.type != "MESH"):
        raise BaseException("cleanupMesh() :: Expected a mesh object")
    removeUnusedVertexGroups(obj)
    removeUnusedShapeKeys(obj)
    removeUnusedCollections()


def removeUnusedVertexGroups(obj):
    if (obj.type != "MESH"):
        return

    obj.update_from_editmode()

    for i, v in sorted(obj.vertex_groups.items(), reverse=True):
        if (v.name.startswith("--")):
            obj.vertex_groups.remove(obj.vertex_groups[i])

    vgroup_used = {i: False for i, k in enumerate(obj.vertex_groups)}
    vgroup_names = {i: k.name for i, k in enumerate(obj.vertex_groups)}

    for v in obj.data.vertices:
        for g in v.groups:
            if g.weight > 0.0:
                vgroup_used[g.group] = True
                vgroup_name = vgroup_names[g.group]
                armatch = re.search(
                    '((.R|.L)(.(\d){1,}){0,1})(?!.)', vgroup_name)
                if armatch != None:
                    tag = armatch.group()
                    mirror_tag = tag.replace(".R", ".L") if armatch.group(
                        2) == ".R" else tag.replace(".L", ".R")
                    mirror_vgname = vgroup_name.replace(tag, mirror_tag)
                    for i, name in sorted(vgroup_names.items(), reverse=True):
                        if mirror_vgname == name:
                            vgroup_used[i] = True
                            break
    for i, used in sorted(vgroup_used.items(), reverse=True):
        if not used:
            obj.vertex_groups.remove(obj.vertex_groups[i])


def removeUnusedShapeKeys(obj):
    if (obj.type != "MESH"):
        return
    if (not obj.data.shape_keys):
        return
    if (not obj.data.shape_keys.use_relative):
        return

    tolerance = 0.001

    kbs = obj.data.shape_keys.key_blocks
    nverts = len(obj.data.vertices)
    to_delete = []

    # Cache locs for rel keys since many keys have the same rel key
    cache = {}

    locs = np.empty(3*nverts, dtype=np.float32)

    for kb in kbs:
        if kb == kb.relative_key:
            continue

        kb.data.foreach_get("co", locs)

        if kb.relative_key.name not in cache:
            rel_locs = np.empty(3*nverts, dtype=np.float32)
            kb.relative_key.data.foreach_get("co", rel_locs)
            cache[kb.relative_key.name] = rel_locs
        rel_locs = cache[kb.relative_key.name]

        locs -= rel_locs
        if (np.abs(locs) < tolerance).all():
            to_delete.append(kb.name)

    for kb_name in to_delete:
        obj.shape_key_remove(obj.data.shape_keys.key_blocks[kb_name])


def removeUnusedMaterials(obj):
    # FIXME: obj wasn't defined
    mat_slots = {}
    for p in obj.data.polygons:
        mat_slots[p.material_index] = 1

    mat_slots = mat_slots.keys()

    for i in reversed(range(len(obj.material_slots))):
        if i not in mat_slots:
            selectAdd(obj)
            obj.active_material_index = i
            bpy.ops.object.material_slot_remove()


def removeUnusedCollections():
    for col in bpy.data.collections:
        if (len(col.all_objects) == 0):
            bpy.data.collections.remove(col)


def cloneToExport(obj):
    if (obj == None):
        raise BaseException(
            "cloneToExport() :: Expected a mesh object, got: None")

    copied = obj.copy()
    if (obj.type == "MESH"):
        copied.data = copied.data.copy()
    bpy.data.collections[EXPORT_COLLECTION].objects.link(copied)
    return copied


def applyModifiers(obj):
    if (obj == None):
        raise BaseException(
            "applyModifiers() :: Expected a mesh object, got: None")

    selectAdd(obj)

    for modifier in obj.modifiers:
        if (modifier.name == "Armature" or modifier.name.startswith("--")):
            bpy.ops.object.modifier_remove(modifier=modifier.name)
        else:
            bpy.ops.object.modifier_apply(modifier=modifier.name)

    try:
        bpy.ops.object.transform_apply(
            location=True, rotation=True, scale=True)
    except:
        None

    deselectAll()


def mergeOntoTarget(targetName, sourceName, armature=None):
    source = bpy.context.scene.objects.get(sourceName)

    # Create target if it doesn't exist
    target = bpy.context.scene.objects.get(targetName)
    if (target != None):
        # Clone source to be merged onto the target
        source = cloneToExport(source)
        applyModifiers(source)

        # print("    [ merge layer ] Copied  " + source.name + "  to merge on  " + targetName)

        # Ensure UV Maps match
        assertUVMatch(target, source)

        # Merge source onto target
        deselectAll()
        selectAdd(source)
        selectAdd(target)

        # Join
        bpy.ops.object.join()
    else:
        # Clone source to be renamed as the new target
        source = cloneToExport(source)
        source.name = targetName
        source.data.name = targetName
        applyModifiers(source)

        # print("    [ new layer ] Copied  " + source.name + "  as  " + targetName)

        if (armature != None):
            source.modifiers.new(name="Armature", type="ARMATURE")
            source.modifiers["Armature"].object = armature
            source.parent = armature
        else:
            source.parent = None


def getAvatarArmature(targetAvatar):
    for obj in bpy.data.objects:
        if (obj.type == "ARMATURE"):
            key = getProp(obj, PROP_AVATAR)
            if (key != None):
                if (key == targetAvatar):
                    return obj
    return None


def getAvatarMeshes(avatar):
    meshes = []
    for obj in bpy.data.objects:
        if (obj.type == "MESH"):
            key = getProp(obj, PROP_TARGET_AVATARS)
            if (key != None):
                keySplit = key.split(",")
                for path in keySplit:
                    pathStart = path.strip()[:len(avatar) + 1]
                    if (pathStart == avatar + "/"):
                        meshes.append(obj.name)
    return meshes


def listAvatarArmatures():
    armatures = []
    for obj in bpy.data.objects:
        if (obj.type == "ARMATURE"):
            key = getProp(obj, PROP_AVATAR)
            if (key != None and key not in armatures):
                armatures.append(obj.name)
    return armatures


#############################################


def getProp(obj, key):
    for k in obj.keys():
        if (k == key):
            return obj[key].strip()
    return None


def showMessageBox(message="", title="Message Box", icon="INFO"):
    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


def selectCollection(name):
    collections = bpy.context.view_layer.layer_collection.children
    for collection in collections:
        if collection.name == name:
            bpy.context.view_layer.active_layer_collection = collection
            return collection
    return None


def selectAdd(obj, state=True):
    for col in obj.users_collection:
        col.hide_viewport = False
    obj.hide_set(False)
    obj.select_set(state)
    bpy.context.view_layer.objects.active = obj


def assertUVMatch(obj1, obj2):
    if (obj1 == None):
        raise BaseException("assertUVMatch() :: Expected an object, got: None")
    if (obj2 == None):
        raise BaseException("assertUVMatch() :: Expected an object, got: None")

    if (len(obj1.data.uv_layers) != len(obj2.data.uv_layers)):
        raise BaseException(
            "Objects have mismatched UV sets: [" + obj1.name + "] [" + obj2.name + "]")


def assertExists(name):
    obj = bpy.context.scene.objects.get(name)
    obj.hide_set(False)
    obj.select_set(False)


def deselectAll():
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")


# returns bone or None that is most likely to be the bone_desc_name described in bones_map
def find_bone(armature: bpy.types.Armature, bone_desc_name: str) -> bpy.types.EditBone:
    def debug_print(*msgs):
        # print("   ", *msgs)
        return

    if not isinstance(bone_desc_name, str):
        raise TypeError("bone_desc_name must be type str")

    # If bone_name not in bones_map, throw exception
    if bone_desc_name not in BONE_DESC_MAP:
        raise TypeError(
            "["
            + bone_desc_name +
            "] not in bones_map! Expected an exact name of a Bone Descriptor."
        )

    def probability_parent(bone_desc_name, bone, stop_counter=0):
        def debug_print(*msgs):
            # print("   ", "   ", *msgs)
            return

        if not isinstance(bone_desc_name, str):
            raise TypeError("bone_desc_name must be type str")

        # This check only happens if there is a parent to compare
        if bone.parent and BONE_DESC_MAP[bone_desc_name]["parent"] and stop_counter < 3:
            parent_name = bone.parent.name

            # Parent descriptor
            parent_desc_name = BONE_DESC_MAP[bone_desc_name]["parent"]

            # If exact match, return bone
            if parent_name == parent_desc_name:
                debug_print("* Exact match ",  parent_name,
                            " == ", parent_desc_name)
                return 1

            debug_print("Comparing ", parent_name, " to ",  parent_desc_name)

            # If the parent is a match, return the bone
            if 0.8 <= similarity_to_common_names(parent_name, parent_desc_name):
                debug_print(bone.name, " seems to be ", bone_desc_name)
                return probability_parent(parent_desc_name, bone.parent, stop_counter + 1)
            else:
                debug_print("* Not a match!")
                return 0

        s = similarity_to_common_names(bone.name, bone_desc_name)
        s += 0.1 * stop_counter
        if 0.8 <= s:
            debug_print("* Likely match: ", bone.name, " == ", bone_desc_name)
            return s
        else:
            debug_print("* Not a match!")
            return 0

    def check_child(bone_desc_name, bone):
        def debug_print(*msgs):
            # print("   ", "   ", *msgs)
            return

        if not isinstance(bone_desc_name, str):
            raise TypeError("bone_desc_name must be type str")

        for child_bone in bone.children:
            child_name = child_bone.name

            debug_print("Checking child:", child_name)

            # Child descriptor
            for child_desc_name in BONE_DESC_MAP[bone_desc_name]["children"]:
                debug_print("Comparing it to:", child_desc_name)

                # If exact match, return bone
                if child_name == child_desc_name:
                    debug_print("* Exact match ",  child_name,
                                " == ", child_desc_name)
                    return True

                # If the child is a match, return the bone
                if 0.8 <= similarity_to_common_names(child_name, child_desc_name):
                    debug_print("* Child is a good match",
                                bone.name, " is ", bone_desc_name)
                    return True

        return False

    debug_print("find_bone(", bone_desc_name, ")")

    # Switch to Edit mode
    bpy.ops.object.mode_set(mode="EDIT")

    bone_matches = []

    # All bones in armature that are similar to the common_names
    for bone in armature.data.edit_bones:
        # If exact match, return bone
        if bone.name == bone_desc_name:
            return bone

        if 0.75 <= similarity_to_common_names(bone.name, bone_desc_name):
            bone_matches.append(bone)

    debug_print("Similar names:", [b.name for b in bone_matches])

    if len(bone_matches) == 0:
        return None

    # Loop over bone_matches and store pairs of [likeliness, bone]
    likely_bone = []
    for bone in bone_matches:
        if bone.parent:
            if probability_parent(bone_desc_name, bone):
                likely_bone.append([
                    similarity_to_common_names(bone.name, bone_desc_name),
                    bone
                ])

    # If a likely one was found, return the max of likely_bone[1]
    if len(likely_bone):
        debug_print("Very likely matches:", [(b[1].name) for b in likely_bone])
        return max(likely_bone, key=lambda b: b[0])[1]

    # Check immediate bones, and if they look like what BONE_DESC_MAP describes, add them to likely_bone
    if bone.children:
        for bone in bone_matches:
            if check_child(bone_desc_name, bone):
                likely_bone.append([
                    similarity_to_common_names(bone.name, bone_desc_name),
                    bone
                ])

        debug_print("Likely matches:", [(b[1].name) for b in likely_bone])

        # If a likely one was found, return it
        if len(likely_bone):
            debug_print("Very likely matches:", [
                        (b[1].name) for b in likely_bone])
            return max(likely_bone, key=lambda b: b[0])[1]

    return None


def find_pose_bone(armature: bpy.types.Armature, bone_desc_name: str) -> bpy.types.PoseBone:
    if not isinstance(bone_desc_name, str):
        raise TypeError("bone_desc_name must be type str")

    bone = find_bone(armature, bone_desc_name)

    if bone:
        return armature.pose.bones[bone.name]
    else:
        return None


def similarity_to_common_names(bone_name: str, bone_desc_name: str) -> float:
    if not isinstance(bone_desc_name, str):
        raise TypeError("bone_desc_name must be type str")

    # Regex removes substr .001, .002, etc. from name
    bone_name = re.sub(r"\.\d{3}", "", bone_name)
    bone_name = re.sub(r"_", ".", bone_name)

    common_names = BONE_DESC_MAP[bone_desc_name]["common_names"]
    if common_names:
        # Return largest string_similarity value
        return max(
            string_similarity(bone_name, common_name)
            for common_name in common_names
        )
    else:
        return string_similarity(bone_name, bone_desc_name)


def string_similarity(str1: str, str2: str) -> float:
    if not isinstance(str1, str):
        raise TypeError("str1 must be str type")
    if not isinstance(str2, str):
        raise TypeError("str2 must be str type")

    # , substring_length: Optional[int] = 2, case_sensitive: Optional[bool] = False
    substring_length = 2
    case_sensitive = False

    if not case_sensitive:
        str1 = str1.lower()
        str2 = str2.lower()
    if len(str1) < substring_length or len(str2) < substring_length:
        return 0
    substr_count1 = defaultdict(int)
    for i in range(len(str1) - substring_length + 1):
        substr1 = str1[i:i+substring_length]
        substr_count1[substr1] += 1
    match = 0
    for j in range(len(str2) - substring_length + 1):
        substr2 = str2[j:j+substring_length]
        count = substr_count1[substr2]
        if count > 0:
            substr_count1[substr2] = count - 1
            match += 1
    return (match * 2) / (len(str1) + len(str2) - ((substring_length - 1) * 2))


def find_meshes_affected_by_armature_modifier(armature):
    ret = []
    for obj in bpy.data.objects:
        # Must be a mesh
        if obj.type != "MESH":
            continue

        mesh = obj

        # Must be using this armature in the "Armature" modifier
        # KNOWN ISSUE: If the mesh uses this armature in 2 armature modifiers, something not good will happen
        using_armature = False
        which_modifier = None
        for mod in mesh.modifiers:
            if mod.type == "ARMATURE":
                if mod.object == armature:
                    using_armature = True
                    which_modifier = mod
                    break
        if not using_armature:
            continue

        # Add to affected_meshes pair: [ mesh, modifier ]
        ret.append([mesh, which_modifier])

    return ret


# Apply pose onto all meshes (retains the Armature modifier)
def apply_pose(armature, mesh_modifier_pairs):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="DESELECT")

    for mesh, modifier in mesh_modifier_pairs:
        # Select the mesh
        mesh.select_set(True)
        bpy.context.view_layer.objects.active = mesh

        debug_print("Applying pose to mesh ", mesh.name, modifier.name)
        # Duplicate modifier & apply it
        modifier_copy = mesh.modifiers.new(modifier.name, modifier.type)
        debug_print("Copied modifier", modifier_copy.name)
        modifier_copy.object = modifier.object
        modifier_copy.use_deform_preserve_volume = True

        # If shape keys exist (note that shape_keys may be None)
        if mesh.data.shape_keys != None:
            applyModifierForObjectWithShapeKeys(
                bpy.context, [modifier_copy.name], True)
        else:
            bpy.ops.object.modifier_apply(modifier=modifier_copy.name)

        # Unselect
        mesh.select_set(False)
        bpy.context.view_layer.objects.active = None

    # Select the armature
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

    # Set pose as rest pose
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply()


# Clear all pose bones that may be in a pose
def clear_pose(armature):
    for bone in armature.pose.bones:
        bone.matrix_basis.identity()


# Align a bone onto an axis
# def align_bone_to_axis(armature, bone, axis, direction):
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
        debug_print("rd: ", rd)

        # Matrix that rotates bone to v
        M = (
            Matrix.Translation(head) @
            rd.to_matrix().to_4x4() @
            Matrix.Translation(-head)
        )

        bone.matrix = M @ bone.matrix

    bone_name = bone.name

    if needs_align(bone, axis_x, axis_y, axis_z):
        # If bone ends in .L or .R, apply it on the mirrored bone as well
        if bone_name.endswith(".L") or bone_name.endswith(".R"):
            # Run on bone
            _helper_align(bone, axis_x, axis_y, axis_z)

            # And then the mirrored bone
            mirrored_bone_name = BONE_DESC_MAP[bone_name]["mirror"]

            # If bone a type of bpy.types.PoseBone, use find_pose_bone
            if isinstance(bone, bpy.types.PoseBone):
                mirrored_bone = find_pose_bone(armature, mirrored_bone_name)
            else:
                mirrored_bone = find_bone(armature, mirrored_bone_name)

            if mirrored_bone != None:
                debug_print("Mirrored bone found: ", mirrored_bone_name)

                # Run on mirrored bone
                _helper_align(mirrored_bone, -axis_x, axis_y, axis_z)
        else:
            # Run it as requested
            _helper_align(bone, axis_x, axis_y, axis_z)

        return True
    else:
        return False


def normalize_armature_rename_bones(armature: bpy.types.Armature):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    debug_print("Starting normalize_armature_rename_bones()")

    # Iterate over descriptors in BONE_DESC_MAP & rename if not the desired name
    for bone_desc_name in BONE_DESC_MAP:
        bone_desc = BONE_DESC_MAP[bone_desc_name]

        bone = find_bone(armature, bone_desc_name)
        if bone == None:
            debug_print("Couldn't find bone: ", bone_desc_name)
            continue

        if bone.name == bone_desc_name:
            debug_print("Name is good: ", bone.name)

        # Do rename
        if bone.name != bone_desc_name:
            debug_print("Renaming: ", bone.name, " to ", bone_desc_name)
            bone.name = bone_desc_name

        # Check if bone is connected
        if "connected" in bone_desc and bone_desc["connected"]:
            if not bone.use_connect:
                debug_print("Connecting bone: ", bone.name)

                # Move parent's tail to this head
                bone.parent.tail = bone.head

                bone.use_connect = True
        else:
            if bone.use_connect:
                debug_print("Detaching bone: ", bone.name)

                bone.use_connect = False


def normalize_armature_t_pose(armature: bpy.types.Armature):
    def debug_print(*msgs):
        print("   ", *msgs)
        return

    debug_print("Starting normalize_armature_t_pose()")

    # Find all meshes that have an armature modifier with this armature
    affected_meshes = find_meshes_affected_by_armature_modifier(armature)

    clear_pose(armature)

    should_apply = False

    ################
    # Ankle Initialization - Edit and point Ankle bone forward

    align_bone_to_axis(armature, find_bone(armature, "Ankle.L"), 0, -1, 0)
    align_bone_to_axis(armature, find_bone(armature, "Ankle.R"), 0, -1, 0)
    align_bone_to_axis(armature, find_bone(armature, "Toe.L"), 0, -1, 0)
    align_bone_to_axis(armature, find_bone(armature, "Toe.R"), 0, -1, 0)

    ################
    # Body Round 1

    # Align "Hips" to z-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Hips"), 0, 0, 1):
        should_apply = True

    # Move "Hips" to y=0
    hips = find_pose_bone(armature, "Hips")
    if hips.matrix.translation.y != 0:
        hips.matrix.translation.y = 0
        should_apply = True

    if should_apply:
        apply_pose(armature, affected_meshes)
        should_apply = False

    ################
    # Body Round 2

    # Align "Spine" to z-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Spine"), 0, 0, 1):
        should_apply = True

    # Align "Thigh" to z-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Thigh.L"), 0, 0, -1):
        should_apply = True

    if should_apply:
        apply_pose(armature, affected_meshes)
        should_apply = False

    ################
    # Body Round 3

    # Align "Chest" to z-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Chest"), 0, 0, 1):
        should_apply = True

    # Align "Knee" to z-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Knee.L"), 0, 0, -1):
        should_apply = True

    if should_apply:
        apply_pose(armature, affected_meshes)
        should_apply = False

    ################
    # Body Round 4

    # Align "Neck" to z-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Neck"), 0, 0, 1):
        should_apply = True

    # Move "Neck" to z=0
    neck = find_pose_bone(armature, "Neck")
    if neck.matrix.translation.y != 0:
        neck.matrix.translation.y = 0
        should_apply = True

    # Move "Shoulder" to z=0
    shoulder_l = find_pose_bone(armature, "Shoulder.L")
    shoulder_r = find_pose_bone(armature, "Shoulder.R")
    if shoulder_l.matrix.translation.y != 0 or shoulder_r.matrix.translation.y != 0:
        shoulder_l.matrix.translation.y = 0
        shoulder_r.matrix.translation.y = 0
        should_apply = True

    # Align "Ankle" to y-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Ankle.L"), 0, -1, 0):
        should_apply = True

    if should_apply:
        apply_pose(armature, affected_meshes)
        should_apply = False

    ################
    # Body Round 5

    # Align "Head" to z-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Head"), 0, 0, 1):
        should_apply = True

    # Align "Toe" to y-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Toe.L"), 0, -1, 0):
        should_apply = True

    if should_apply:
        apply_pose(armature, affected_meshes)
        should_apply = False

    ################
    # The rest of the arm

    # Align "Shoulder" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Shoulder.L"), 1, 0, 0):
        apply_pose(armature, affected_meshes)

    # Align "Arm" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Arm.L"), 1, 0, 0):
        apply_pose(armature, affected_meshes)

    # Align "Elbow" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Elbow.L"), 1, 0, 0):
        apply_pose(armature, affected_meshes)

    # Align "Wrist" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Wrist.L"), 1, 0, 0):
        apply_pose(armature, affected_meshes)

    ################
    # Fingers Round 1

    # Align "Thumb 1" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Thumb 1.L"), 1, -1, 0):
        should_apply = True

    # Align "Index Finger 1" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Index Finger 1.L"), 1, 0, 0):
        should_apply = True

    # Align "Middle Finger 1" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Middle Finger 1.L"), 1, 0, 0):
        should_apply = True

    # Align "Ring Finger 1" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Ring Finger 1.L"), 1, 0, 0):
        should_apply = True

    # Align "Little Finger 1" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Little Finger 1.L"), 1, 0, 0):
        should_apply = True

    if should_apply:
        apply_pose(armature, affected_meshes)
        should_apply = False

    ################
    # Fingers Round 2

    # Align "Thumb 2" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Thumb 2.L"), 1, -1, 0):
        should_apply = True

    # Align "Index Finger 2" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Index Finger 2.L"), 1, 0, 0):
        should_apply = True

    # Align "Middle Finger 2" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Middle Finger 2.L"), 1, 0, 0):
        should_apply = True

    # Align "Ring Finger 2" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Ring Finger 2.L"), 1, 0, 0):
        should_apply = True

    # Align "Little Finger 2" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Little Finger 2.L"), 1, 0, 0):
        should_apply = True

    if should_apply:
        apply_pose(armature, affected_meshes)
        should_apply = False

    ################
    # Fingers Round 3

    # Align "Thumb 3" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Thumb 3.L"), 1, -1, 0):
        should_apply = True

    # Align "Index Finger 3" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Index Finger 3.L"), 1, 0, 0):
        should_apply = True

    # Align "Middle Finger 3" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Middle Finger 3.L"), 1, 0, 0):
        should_apply = True

    # Align "Ring Finger 3" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Ring Finger 3.L"), 1, 0, 0):
        should_apply = True

    # Align "Little Finger 3" to x-axis
    if align_bone_to_axis(armature, find_pose_bone(armature, "Little Finger 3.L"), 1, 0, 0):
        should_apply = True

    if should_apply:
        apply_pose(armature, affected_meshes)
        should_apply = False

    ################
    # Switch to pose mode

    clear_pose(armature)

    bpy.ops.object.mode_set(mode="POSE")


def normalize_armature_roll_bones(armature: bpy.types.Armature):
    def debug_print(*msgs):
        # print("   ", *msgs)
        return

    debug_print("Starting normalize_armature_roll_bones()")

    # Switch to edit mode
    bpy.ops.object.mode_set(mode="EDIT")

    # Iterate over descriptors in BONE_DESC_MAP & reset their roll
    for bone_desc_name in BONE_DESC_MAP:
        bone_desc = BONE_DESC_MAP[bone_desc_name]

        # Get bone
        bone = armature.data.edit_bones[bone_desc_name]

        desc_roll = 0
        if "roll" in bone_desc and bone_desc["roll"] != None:
            # Get roll as radians
            desc_roll = bone_desc["roll"] * (math.pi / 180)

        if bone.roll != desc_roll:
            debug_print("Setting roll of", bone.name, "to", desc_roll)
            bone.roll = desc_roll


#############################################
# Operators


class NyaaToolsNormalizeArmature(Operator):
    """Normalizes armatures to my preferred layout"""
    bl_idname = "nyaa.normalize_armature"
    bl_label = "Normalize Armature"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            obj = bpy.context.active_object

            if obj == None:
                self.report(
                    {"ERROR"}, "Please select an armature object first! Got: None")
                return {"CANCELLED"}

            if obj.type != "ARMATURE":
                self.report(
                    {"ERROR"}, "Please select an armature object first! Got: " + obj.type)
                return {"CANCELLED"}

            # {bpy.types.Armature}  The armature to normalize
            armature = obj

            # Rename bones
            normalize_armature_rename_bones(armature)

            # Set T-Pose
            normalize_armature_t_pose(armature)

            # Set T-Pose
            normalize_armature_roll_bones(armature)

            print("Done!")
            print("")

            return {"FINISHED"}

        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


class NyaaToolsInitMods(Operator):
    """Creates my prefered modifier stacks"""
    bl_idname = "nyaa.init_mods"
    bl_label = "Initialize Modifier Stack"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            obj = bpy.context.active_object

            if obj is None:
                self.report({"ERROR"}, "Expected a mesh object, got: None")
                return {"CANCELLED"}

            if obj.type != "MESH":
                self.report(
                    {"ERROR"}, "Expected a mesh object, got: " + obj.type)
                return {"CANCELLED"}

            # Delete all armatures
            for mod in obj.modifiers:
                if (mod.type == "ARMATURE"):
                    obj.modifiers.remove(mod)

            name = "Final - DataTransfer"
            mod = obj.modifiers.get(name)
            if (mod):
                obj.modifiers.remove(mod)
            mod = obj.modifiers.new(name, "DATA_TRANSFER")
            mod.show_expanded = False
            mod.show_on_cage = True
            mod.show_in_editmode = True
            mod.use_vert_data = True
            mod.data_types_verts = {"VGROUP_WEIGHTS"}
            mod.vert_mapping = "POLYINTERP_NEAREST"

            name = "Final - Decimate"
            mod = obj.modifiers.get(name)
            if (mod):
                obj.modifiers.remove(mod)
            mod = obj.modifiers.new(name, "DECIMATE")
            mod.show_expanded = False
            mod.show_render = False
            mod.decimate_type = "COLLAPSE"
            mod.ratio = 0.75
            mod.delimit = {"NORMAL", "MATERIAL", "SEAM", "SHARP", "UV"}
            mod.use_dissolve_boundaries = True

            name = "Final - Triangulate"
            mod = obj.modifiers.get(name)
            if (mod):
                obj.modifiers.remove(mod)
            mod = obj.modifiers.new(name, "TRIANGULATE")
            mod.show_expanded = False
            mod.show_in_editmode = False
            mod.show_render = False
            mod.min_vertices = 5

            # Make an armature for every PROP_TARGET_AVATARS defined
            key = getProp(obj, PROP_TARGET_AVATARS)
            if (key != None):
                keySplit = key.split(",")
                for path in keySplit:
                    pathParts = path.split("/")
                    targetAvatarName = pathParts[0].strip()
                    meshLayerName = pathParts[1].strip()

                    target = getAvatarArmature(targetAvatarName)
                    print(target)
                    if (target != None):
                        name = "--( " + targetAvatarName + " )"
                        mod = obj.modifiers.new(name, "ARMATURE")
                        mod.show_expanded = False
                        mod.show_on_cage = True
                        mod.show_in_editmode = True
                        mod.show_viewport = True
                        mod.show_render = True
                        mod.object = target

        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        return {"FINISHED"}


class NyaaToolsMergeExport(Operator):
    """Merge tools for avatars"""
    bl_idname = "nyaa.merge_tool"
    bl_label = "Nyaa Merge Tool"
    bl_options = {"REGISTER", "UNDO"}

    armatureName: StringProperty(
        name="Armature",
        default=""
    )

    def execute(self, context):
        try:
            # Create "Export" collection
            collectionExport = bpy.data.collections.new("Export")

            bpy.context.scene.collection.children.link(collectionExport)
            collectionExport.color_tag = "COLOR_01"

            armature = bpy.context.scene.objects.get(self.armatureName)
            avatarName = getProp(armature, PROP_AVATAR)

            # Rename all objects to avoid collisions
            for obj in bpy.data.objects:
                obj.name = "____" + obj.name

            # Rename & move Armature to exports
            armature.name = "Armature"
            armature.data.name = "Armature"
            armature.parent = None

            try:
                selectAdd(armature)
                bpy.ops.object.transform_apply(
                    location=True, rotation=True, scale=True)
                bpy.data.collections[EXPORT_COLLECTION].objects.link(armature)
            except:
                None

            # Perform layer merges on meshes
            for meshName in getAvatarMeshes(avatarName):
                mesh = bpy.context.scene.objects.get(meshName)
                if (mesh != None):
                    key = getProp(mesh, PROP_TARGET_AVATARS)
                    if (key != None):
                        keySplit = key.split(",")
                        for path in keySplit:
                            pathParts = path.split("/")
                            targetAvatarName = pathParts[0].strip()
                            meshLayerName = pathParts[1].strip()
                            if (avatarName == targetAvatarName):
                                mergeOntoTarget(
                                    meshLayerName, meshName, armature)
                else:
                    print("    BUG: Mesh doesn't exist, skipping for now:  " + meshName)

            # Cleanup
            for obj in bpy.data.objects:
                if (obj.name.startswith("____")):
                    bpy.data.objects.remove(obj)

            for obj in bpy.data.objects:
                if (obj.type == "MESH"):
                    cleanupMesh(obj)

            for col in bpy.context.scene.collection.children:
                if (col.name != "Export"):
                    bpy.data.collections.remove(col)

            # Export
            selectCollection(EXPORT_COLLECTION)

            if getProp(armature, PROP_EXPORT_PATH):
                path = getProp(armature, PROP_EXPORT_PATH)
                if (path):
                    if (path[-1] == "/" or path[-1] == "\\"):
                        path = bpy.path.abspath(
                            "//" + path + targetAvatarName + ".fbx")
                    else:
                        path = bpy.path.abspath("//" + path)

                bpy.ops.export_scene.fbx(
                    filepath=path,
                    check_existing=False,
                    filter_glob="*.fbx",
                    use_active_collection=True,

                    apply_scale_options="FBX_SCALE_UNITS",
                    axis_forward="-Y",
                    axis_up="Z",
                    use_mesh_modifiers=False,
                    mesh_smooth_type="FACE",
                    # primary_bone_axis="X",
                    # secondary_bone_axis="-Y",
                    add_leaf_bones=False,

                    bake_anim=False
                    # bake_anim_use_all_actions=False,
                )

        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        return {"FINISHED"}


class Link_Button(bpy.types.Operator):
    """Open links in a web browser"""
    bl_idname = "ops.open_link"
    bl_label = "Open Link in web browser"
    bl_options = {"REGISTER"}

    url: StringProperty(name="URL",
                        description="URL",
                        default=""
                        )

    def execute(self, context):
        webbrowser.open_new(self.url)  # opens in default browser
        return {"FINISHED"}


#############################################
# Panel

class NyaaPanel(bpy.types.Panel):
    bl_label = "NyaaTools v" + VERSION
    bl_idname = "OBJECT_PT_NYAAPANEL"
    bl_category = "Tool"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    selectedAvatar: StringProperty(
        name="Selected Avatar",
        default=""
    )

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Helpers", icon="TOOL_SETTINGS")
        box.operator("nyaa.normalize_armature",
                     text=NyaaToolsNormalizeArmature.bl_label, icon="OUTLINER_OB_ARMATURE")
        box.operator("nyaa.init_mods",
                     text=NyaaToolsInitMods.bl_label, icon="MODIFIER")

        box = layout.box()
        box.label(text="Merge & Export", icon="OUTLINER_OB_ARMATURE")
        armatures = listAvatarArmatures()
        for armatureName in armatures:
            armature = bpy.context.scene.objects.get(armatureName)
            if (armature):
                text = getProp(armature, PROP_AVATAR)
                if (0 < len(text)):
                    text = text
                    box.operator("nyaa.merge_tool",
                                 text=text).armatureName = armatureName

        layout.separator()

        box = layout.box()
        box.label(text="Atelier Nyaarium", icon="INFO")
        box.operator("ops.open_link", text="Discord",
                     icon="WORLD").url = "discord.nyaarium.com"
        box.operator("ops.open_link", text="Other Links",
                     icon="WORLD").url = "nyaarium.com"


CLASSES = [
    NyaaPanel,
    NyaaToolsNormalizeArmature,
    NyaaToolsInitMods,
    NyaaToolsMergeExport,
    Link_Button,
]


def register():
    for klass in CLASSES:
        bpy.utils.register_class(klass)


def unregister():
    for klass in CLASSES:
        bpy.utils.unregister_class(klass)


if __name__ == "__main__":
    register()


#############################################
#############################################
# External Libraries


# ------------------------------------------------------------------------------
# The MIT License (MIT)
#
# Copyright (c) 2015 Przemysław Bągard
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# ------------------------------------------------------------------------------

# Date: 01 February 2015
# Blender script
# Description: Apply modifier and remove from the stack for object with shape keys
# (Pushing 'Apply' button in 'Object modifiers' tab result in an error 'Modifier cannot be applied to a mesh with shape keys').

# bl_info = {
#     "name":         "Apply modifier for object with shape keys",
#     "author":       "Przemysław Bągard, additonal contributions by Iszotic, updated to 2.93 by Fro Zen",
#     "blender":      (2,93,0),
#     "version":      (0,2,1),
#     "location":     "Context menu",
#     "description":  "Apply modifier and remove from the stack for object with shape keys (Pushing 'Apply' button in 'Object modifiers' tab result in an error 'Modifier cannot be applied to a mesh with shape keys').",
#     "category":     "Object Tools > Multi Shape Keys"
# }

def applyModifierForObjectWithShapeKeys(context, selectedModifiers, disable_armatures):

    list_properties = []
    properties = ["interpolation", "mute", "name", "relative_key",
                  "slider_max", "slider_min", "value", "vertex_group"]
    shapesCount = 0
    vertCount = -1
    startTime = time.time()

    disabled_armature_modifiers = []
    if disable_armatures:
        for modifier in context.object.modifiers:
            if modifier.name not in selectedModifiers and modifier.type == 'ARMATURE' and modifier.show_viewport == True:
                disabled_armature_modifiers.append(modifier)
                modifier.show_viewport = False

    if context.object.data.shape_keys:
        shapesCount = len(context.object.data.shape_keys.key_blocks)

    if (shapesCount == 0):
        for modifierName in selectedModifiers:
            bpy.ops.object.modifier_apply(modifier=modifierName)
        return (True, None)

    # We want to preserve original object, so all shapes will be joined to it.
    originalObject = context.view_layer.objects.active
    bpy.ops.object.select_all(action='DESELECT')
    originalObject.select_set(True)

    # Copy object which will holds all shape keys.
    bpy.ops.object.duplicate_move(OBJECT_OT_duplicate={"linked": False, "mode": 'TRANSLATION'}, TRANSFORM_OT_translate={"value": (0, 0, 0), "orient_type": 'GLOBAL', "orient_matrix": ((1, 0, 0), (0, 1, 0), (0, 0, 1)), "orient_matrix_type": 'GLOBAL', "constraint_axis": (False, False, False), "mirror": True, "use_proportional_edit": False, "proportional_edit_falloff": 'SMOOTH',
                                  "proportional_size": 1, "use_proportional_connected": False, "use_proportional_projected": False, "snap": False, "snap_target": 'CLOSEST', "snap_point": (0, 0, 0), "snap_align": False, "snap_normal": (0, 0, 0), "gpencil_strokes": False, "cursor_transform": False, "texture_space": False, "remove_on_cancel": False, "release_confirm": False, "use_accurate": False})
    copyObject = context.view_layer.objects.active
    copyObject.select_set(False)

    # Return selection to originalObject.
    context.view_layer.objects.active = originalObject
    originalObject.select_set(True)

    # Save key shape properties
    for i in range(0, shapesCount):
        key_b = originalObject.data.shape_keys.key_blocks[i]
        print(originalObject.data.shape_keys.key_blocks[i].name, key_b.name)
        properties_object = {p: None for p in properties}
        properties_object["name"] = key_b.name
        properties_object["mute"] = key_b.mute
        properties_object["interpolation"] = key_b.interpolation
        properties_object["relative_key"] = key_b.relative_key.name
        properties_object["slider_max"] = key_b.slider_max
        properties_object["slider_min"] = key_b.slider_min
        properties_object["value"] = key_b.value
        properties_object["vertex_group"] = key_b.vertex_group
        list_properties.append(properties_object)

    # Handle base shape in "originalObject"
    print("applyModifierForObjectWithShapeKeys: Applying base shape key")
    bpy.ops.object.shape_key_remove(all=True)
    for modifierName in selectedModifiers:
        bpy.ops.object.modifier_apply(modifier=modifierName)
    vertCount = len(originalObject.data.vertices)
    bpy.ops.object.shape_key_add(from_mix=False)
    originalObject.select_set(False)

    # Handle other shape-keys: copy object, get right shape-key, apply modifiers and merge with originalObject.
    # We handle one object at time here.
    for i in range(1, shapesCount):
        currTime = time.time()
        elapsedTime = currTime - startTime

        print("applyModifierForObjectWithShapeKeys: Applying shape key %d/%d ('%s', %0.2f seconds since start)" %
              (i+1, shapesCount, list_properties[i]["name"], elapsedTime))
        context.view_layer.objects.active = copyObject
        copyObject.select_set(True)

        # Copy temp object.
        bpy.ops.object.duplicate_move(OBJECT_OT_duplicate={"linked": False, "mode": 'TRANSLATION'}, TRANSFORM_OT_translate={"value": (0, 0, 0), "orient_type": 'GLOBAL', "orient_matrix": ((1, 0, 0), (0, 1, 0), (0, 0, 1)), "orient_matrix_type": 'GLOBAL', "constraint_axis": (False, False, False), "mirror": True, "use_proportional_edit": False, "proportional_edit_falloff": 'SMOOTH',
                                      "proportional_size": 1, "use_proportional_connected": False, "use_proportional_projected": False, "snap": False, "snap_target": 'CLOSEST', "snap_point": (0, 0, 0), "snap_align": False, "snap_normal": (0, 0, 0), "gpencil_strokes": False, "cursor_transform": False, "texture_space": False, "remove_on_cancel": False, "release_confirm": False, "use_accurate": False})
        tmpObject = context.view_layer.objects.active
        bpy.ops.object.shape_key_remove(all=True)
        copyObject.select_set(True)
        copyObject.active_shape_key_index = i

        # Get right shape-key.
        bpy.ops.object.shape_key_transfer()
        context.object.active_shape_key_index = 0
        bpy.ops.object.shape_key_remove()
        bpy.ops.object.shape_key_remove(all=True)

        # Time to apply modifiers.
        for modifierName in selectedModifiers:
            bpy.ops.object.modifier_apply(modifier=modifierName)

        # Verify number of vertices.
        if vertCount != len(tmpObject.data.vertices):
            errorInfo = ("Shape keys ended up with different number of vertices!\n"
                         "All shape keys needs to have the same number of vertices after modifier is applied.\n"
                         "Otherwise joining such shape keys will fail!")
            return (False, errorInfo)

        # Join with originalObject
        copyObject.select_set(False)
        context.view_layer.objects.active = originalObject
        originalObject.select_set(True)
        bpy.ops.object.join_shapes()
        originalObject.select_set(False)
        context.view_layer.objects.active = tmpObject

        # Remove tmpObject
        bpy.ops.object.delete(use_global=False)

    # Restore shape key properties like name, mute etc.
    context.view_layer.objects.active = originalObject
    for i in range(0, shapesCount):
        key_b = context.view_layer.objects.active.data.shape_keys.key_blocks[i]
        key_b.name = list_properties[i]["name"]
        key_b.interpolation = list_properties[i]["interpolation"]
        key_b.mute = list_properties[i]["mute"]
        key_b.slider_max = list_properties[i]["slider_max"]
        key_b.slider_min = list_properties[i]["slider_min"]
        key_b.value = list_properties[i]["value"]
        key_b.vertex_group = list_properties[i]["vertex_group"]
        rel_key = list_properties[i]["relative_key"]

        for j in range(0, shapesCount):
            key_brel = context.view_layer.objects.active.data.shape_keys.key_blocks[j]
            if rel_key == key_brel.name:
                key_b.relative_key = key_brel
                break

    # Remove copyObject.
    originalObject.select_set(False)
    context.view_layer.objects.active = copyObject
    copyObject.select_set(True)
    bpy.ops.object.delete(use_global=False)

    # Select originalObject.
    context.view_layer.objects.active = originalObject
    context.view_layer.objects.active.select_set(True)

    if disable_armatures:
        for modifier in disabled_armature_modifiers:
            modifier.show_viewport = True

    return (True, None)
