import bpy
from bpy.props import *
from bpy.types import (Panel, Operator)
import re
import numpy as np
import webbrowser
from typing import Optional
from collections import defaultdict

# ctx = bpy.context.copy()


#############################################
# Prop Key Constants

VERSION = "0.9"
EXPORT_COLLECTION = "Export"
PROP_AVATAR = "avatar"
PROP_TARGET_AVATARS = "targetAvatars"
PROP_EXPORT_PATH = "exportPath"

# Prop Key Constants
#############################################


# This bone description map is used to
BONE_DESC_MAP = {
    # Bone Descriptions

    "Hips": {
        "common_names": ["Hips", "Hip", "Pelvis"],
        "parent": None,
        "children": ["Spine", "Thigh.L", "Thigh.R"],
        "mirror": None
    },
    "Spine": {
        "common_names": ["Spine"],
        "parent": "Hips",
        "children": ["Chest"],
        "mirror": None
    },
    "Chest": {
        "common_names": ["Chest", "Breast Root", "Shoulder.L", "Shoulder.R"],
        "parent": "Spine",
        "children": ["Neck"],
        "mirror": None
    },
    "Neck": {
        "common_names": ["Neck"],
        "parent": "Chest",
        "children": ["Head"],
        "mirror": None
    },
    "Head": {
        "common_names": ["Head"],
        "parent": "Neck",
        "children": ["Eye.L", "Eye.R"],
        "mirror": None
    },
    "Eye.L": {
        "common_names": ["Eye.L", "Left Eye"],
        "parent": "Head",
        "children": None,
        "mirror": "Eye.R"
    },
    "Eye.R": {
        "common_names": ["Eye.R", "Right Eye"],
        "parent": "Head",
        "children": None,
        "mirror": "Eye.L"
    },

    "Breast Root": {
        "common_names": ["Breast Root"],
        "parent": "Spine",
        "children": ["Breast.R", "Breast.L"],
        "mirror": None
    },
    "Breast.R": {
        "common_names": ["Breast", "Right Breast"],
        "parent": "Breast Root",
        "children": None,
        "mirror": "Breast.L"
    },
    "Breast.L": {
        "common_names": ["Breast", "Left Breast"],
        "parent": "Breast Root",
        "children": None,
        "mirror": "Breast.R"
    },

    "Thigh.L": {
        "common_names": ["Thigh.L", "Leg.L", "Upper Leg.L", "Left Leg"],
        "parent": "Hips",
        "children": ["Knee.L"],
        "mirror": "Thigh.R"
    },
    "Knee.L": {
        "common_names": ["Knee.L", "Lower Leg.L", "Left Knee"],
        "parent": "Thigh.L",
        "children": ["Left Ankle"],
        "mirror": "Knee.R"
    },
    "Ankle.L": {
        "common_names": ["Knee.L", "Left Ankle", "Foot.L", "Left Foot"],
        "parent": "Knee.L",
        "children": ["Toe.L"],
        "mirror": "Ankle.R"
    },
    "Toe.L": {
        "common_names": ["Toe.L", "Left Toe"],
        "parent": "Ankle.L",
        "children": None,
        "mirror": "Toe.R"
    },

    "Thigh.R": {
        "common_names": ["Thigh.R", "Leg.R", "Upper Leg.R", "Right Leg"],
        "parent": "Hips",
        "children": ["Knee.R"],
        "mirror": "Thigh.L"
    },
    "Knee.R": {
        "common_names": ["Knee.R", "Lower Leg.R", "Right Knee"],
        "parent": "Thigh.R",
        "children": ["Right Ankle"],
        "mirror": "Knee.L"
    },
    "Ankle.R": {
        "common_names": ["Knee.R", "Right Ankle", "Foot.R", "Right Foot"],
        "parent": "Knee.R",
        "children": ["Toe.R"],
        "mirror": "Ankle.L"
    },
    "Toe.R": {
        "common_names": ["Toe.R", "Right Toe"],
        "parent": "Ankle.R",
        "children": None,
        "mirror": "Toe.L"
    },

    "Shoulder.L": {
        "common_names": ["Shoulder.L", "Left Shoulder"],
        "parent": "Chest",
        "children": ["Arm.L"],
        "mirror": "Shoulder.R"
    },
    "Arm.L": {
        "common_names": ["Arm.L", "Upper Arm.L", "Left Arm"],
        "parent": "Shoulder.L",
        "children": ["Elbow.L"],
        "mirror": "Arm.R"
    },
    "Elbow.L": {
        "common_names": ["Elbow.L", "Left Elbow", "Lower Arm.L"],
        "parent": "Arm.L",
        "children": ["Wrist.L"],
        "mirror": "Elbow.R"
    },
    "Wrist.L": {
        "common_names": ["Wrist.L", "Left Wrist", "Hand.L"],
        "parent": "Elbow.L",
        "children": ["Thumb 1.L", "Little Finger 1.L", "Ring Finger 1.L", "Middle Finger 1.L", "Index Finger 1.L"],
        "mirror": "Wrist.R"
    },

    "Shoulder.R": {
        "common_names": ["Shoulder.R", "Right Shoulder"],
        "parent": "Chest",
        "children": ["Arm.R"],
        "mirror": "Shoulder.L"
    },
    "Arm.R": {
        "common_names": ["Arm.R", "Upper Arm.R", "Right Arm"],
        "parent": "Shoulder.R",
        "children": ["Elbow.R"],
        "mirror": "Arm.L"
    },
    "Elbow.R": {
        "common_names": ["Elbow.R", "Right Elbow", "Lower Arm.R"],
        "parent": "Arm.R",
        "children": ["Wrist.R"],
        "mirror": "Elbow.L"
    },
    "Wrist.R": {
        "common_names": ["Wrist.R", "Right Wrist", "Hand.R"],
        "parent": "Elbow.R",
        "children": ["Thumb 1.R", "Little Finger 1.R", "Ring Finger 1.R", "Middle Finger 1.R", "Index Finger 1.R"],
        "mirror": "Wrist.L"
    },

    "Thumb 1.L": {
        "common_names": ["Thumb0_L"],
        "parent": "Wrist.L",
        "children": ["Thumb 2.L"],
        "mirror": "Thumb 1.R"
    },
    "Thumb 2.L": {
        "common_names": ["Thumb1_L"],
        "parent": "Thumb 1.L",
        "children": ["Thumb 3.L"],
        "mirror": "Thumb 2.R"
    },
    "Thumb 3.L": {
        "common_names": ["Thumb2_L"],
        "parent": "Thumb 2.L",
        "children": None,
        "mirror": "Thumb 3.R"
    },
    "Index Finger 1.L": {
        "common_names": ["IndexFinger1_L"],
        "parent": "Wrist.L",
        "children": ["Index Finger 2.L"],
        "mirror": "Index Finger 1.R"
    },
    "Index Finger 2.L": {
        "common_names": ["IndexFinger2_L"],
        "parent": "Index Finger 1.L",
        "children": ["Index Finger 3.L"],
        "mirror": "Index Finger 2.R"
    },
    "Index Finger 3.L": {
        "common_names": ["IndexFinger3_L"],
        "parent": "Index Finger 2.L",
        "children": None,
        "mirror": "Index Finger 3.R"
    },
    "Middle Finger 1.L": {
        "common_names": ["MiddleFinger1_L"],
        "parent": "Wrist.L",
        "children": ["Middle Finger 2.L"],
        "mirror": "Middle Finger 1.R"
    },
    "Middle Finger 2.L": {
        "common_names": ["MiddleFinger2_L"],
        "parent": "Middle Finger 1.L",
        "children": ["Middle Finger 3.L"],
        "mirror": "Middle Finger 2.R"
    },
    "Middle Finger 3.L": {
        "common_names": ["MiddleFinger3_L"],
        "parent": "Middle Finger 2.L",
        "children": None,
        "mirror": "Middle Finger 3.R"
    },
    "Ring Finger 1.L": {
        "common_names": ["RingFinger1_L"],
        "parent": "Wrist.L",
        "children": ["Ring Finger 2.L"],
        "mirror": "Ring Finger 1.R"
    },
    "Ring Finger 2.L": {
        "common_names": ["RingFinger2_L"],
        "parent": "Ring Finger 1.L",
        "children": ["Ring Finger 3.L"],
        "mirror": "Ring Finger 2.R"
    },
    "Ring Finger 3.L": {
        "common_names": ["RingFinger3_L"],
        "parent": "Ring Finger 2.L",
        "children": None,
        "mirror": "Ring Finger 3.R"
    },
    "Little Finger 1.L": {
        "common_names": ["LittleFinger1_L"],
        "parent": "Wrist.L",
        "children": ["Little Finger 2.L"],
        "mirror": "Little Finger 1.R"
    },
    "Little Finger 2.L": {
        "common_names": ["LittleFinger2_L"],
        "parent": "Little Finger 1.L",
        "children": ["Little Finger 3.L"],
        "mirror": "Little Finger 2.R"
    },
    "Little Finger 3.L": {
        "common_names": ["LittleFinger3_L"],
        "parent": "Little Finger 2.L",
        "children": None,
        "mirror": "Little Finger 3.R"
    },

    "Thumb 1.R": {
        "common_names": ["Thumb0_R"],
        "parent": "Wrist.R",
        "children": ["Thumb 2.R"],
        "mirror": "Thumb 1.L"
    },
    "Thumb 2.R": {
        "common_names": ["Thumb1_R"],
        "parent": "Thumb 1.R",
        "children": ["Thumb 3.R"],
        "mirror": "Thumb 2.L"
    },
    "Thumb 3.R": {
        "common_names": ["Thumb2_R"],
        "parent": "Thumb 2.R",
        "children": None,
        "mirror": "Thumb 3.L"
    },
    "Index Finger 1.R": {
        "common_names": ["IndexFinger1_R"],
        "parent": "Wrist.R",
        "children": ["Index Finger 2.R"],
        "mirror": "Index Finger 1.L"
    },
    "Index Finger 2.R": {
        "common_names": ["IndexFinger2_R"],
        "parent": "Index Finger 1.R",
        "children": ["Index Finger 3.R"],
        "mirror": "Index Finger 2.L"
    },
    "Index Finger 3.R": {
        "common_names": ["IndexFinger3_R"],
        "parent": "Index Finger 2.R",
        "children": None,
        "mirror": "Index Finger 3.L"
    },
    "Middle Finger 1.R": {
        "common_names": ["MiddleFinger1_R"],
        "parent": "Wrist.R",
        "children": ["Middle Finger 2.R"],
        "mirror": "Middle Finger 1.L"
    },
    "Middle Finger 2.R": {
        "common_names": ["MiddleFinger2_R"],
        "parent": "Middle Finger 1.R",
        "children": ["Middle Finger 3.R"],
        "mirror": "Middle Finger 2.L"
    },
    "Middle Finger 3.R": {
        "common_names": ["MiddleFinger3_R"],
        "parent": "Middle Finger 2.R",
        "children": None,
        "mirror": "Middle Finger 3.L"
    },
    "Ring Finger 1.R": {
        "common_names": ["RingFinger1_R"],
        "parent": "Wrist.R",
        "children": ["Ring Finger 2.R"],
        "mirror": "Ring Finger 1.L"
    },
    "Ring Finger 2.R": {
        "common_names": ["RingFinger2_R"],
        "parent": "Ring Finger 1.R",
        "children": ["Ring Finger 3.R"],
        "mirror": "Ring Finger 2.L"
    },
    "Ring Finger 3.R": {
        "common_names": ["RingFinger3_R"],
        "parent": "Ring Finger 2.R",
        "children": None,
        "mirror": "Ring Finger 3.L"
    },
    "Little Finger 1.R": {
        "common_names": ["LittleFinger1_R"],
        "parent": "Wrist.R",
        "children": ["Little Finger 2.R"],
        "mirror": "Little Finger 1.L"
    },
    "Little Finger 2.R": {
        "common_names": ["LittleFinger2_R"],
        "parent": "Little Finger 1.R",
        "children": ["Little Finger 3.R"],
        "mirror": "Little Finger 2.L"
    },
    "Little Finger 3.R": {
        "common_names": ["LittleFinger3_R"],
        "parent": "Little Finger 2.R",
        "children": None,
        "mirror": "Little Finger 3.L"
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


def removeUnusedMaterials():
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
def find_bone(armature, bone_desc_name: str) -> bpy.types.EditBone:
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

    def check_parent(bone_desc_name, bone, stop_counter=2):
        def debug_print(*msgs):
            # print("   ", "   ", *msgs)
            return

        if not isinstance(bone_desc_name, str):
            raise TypeError("bone_desc_name must be type str")

        # This check only happens if there is a parent to compare
        if bone.parent and BONE_DESC_MAP[bone_desc_name]["parent"] and 0 < stop_counter:
            parent_name = bone.parent.name

            # Parent descriptor
            parent_desc_name = BONE_DESC_MAP[bone_desc_name]["parent"]
            debug_print("Comparing ",  parent_name, " to:", parent_desc_name)

            # If the parent is a match, return the bone
            if 0.8 <= similarity_to_common_names(parent_name, parent_desc_name):
                debug_print(bone.name, " seems to be ", bone_desc_name)
                return check_parent(parent_desc_name, bone.parent, stop_counter - 1)
            else:
                debug_print("* Not a match!")
                return 0

        s = similarity_to_common_names(bone.name, bone_desc_name)
        if 0.8 <= s:
            debug_print("* Likely match: ", bone.name, " == ", bone_desc_name)
            return s
        else:
            debug_print("* Not a match!")
            return 0

    debug_print("find_bone(", bone_desc_name, ")")

    # Switch to Edit mode
    bpy.ops.object.mode_set(mode="EDIT")

    bone_matches = []

    # All bones in armature that are similar to the common_names
    for bone in armature.data.edit_bones:
        # If exact match, return bone
        if bone.name == bone_desc_name:
            return bone

        if 0.8 <= similarity_to_common_names(bone.name, bone_desc_name):
            bone_matches.append(bone)

    debug_print("Similar names:", [b.name for b in bone_matches])

    if len(bone_matches) == 0:
        return None

    # Loop over bone_matches and store pairs of [likeliness, bone]
    likely_bone = []
    for bone in bone_matches:
        if bone.parent:
            if check_parent(bone_desc_name, bone):
                likely_bone.append([
                    similarity_to_common_names(bone.name, bone_desc_name),
                    bone
                ])

    # DEBUG DISABLE
    likely_bone = []  # DEBUG DISABLE
    # DEBUG DISABLE

    # If a likely one was found, return it
    if len(likely_bone):
        debug_print("Very likely matches:", [(b[1].name) for b in likely_bone])
        return max(likely_bone)[1]

    # Check immediate bones, and if they look like what BONE_DESC_MAP describes, add them to likely_bone

    def check_child(bone_desc_name, bone) -> bpy.types.EditBone:
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

                # If the child is a match, return the bone
                if 0.8 <= similarity_to_common_names(child_name, child_desc_name):
                    debug_print("Child is a good match",
                                bone.name, " is ", bone_desc_name)
                    return bone

        return None

    # If there is no parent to compare, check children
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
            return max(likely_bone)[1]

    return None


def similarity_to_common_names(bone_name: str, bone_desc_name: str) -> bool:
    if not isinstance(bone_desc_name, str):
        raise TypeError("bone_desc_name must be type str")

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


#############################################
# Operators


class NyaaToolsNormalizeArmature(Operator):
    """Normalizes armatures to my preferred layout"""
    bl_idname = "nyaa.normalize_armature"
    bl_label = "Normalize Armature"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = bpy.context.active_object

        if obj == None:
            self.report({"ERROR"}, "Expected an armature object, got: None")
            return {"CANCELLED"}

        if obj.type != "ARMATURE":
            self.report(
                {"ERROR"}, "Expected an armature object, got: " + obj.type)
            return {"CANCELLED"}

        armature = obj

        # Normalize the root bone
        # fixArmatureRoot(obj)

        print("")
        print("")
        print("")
        print("")
        print("")
        print("")

        print("Hips", find_bone(armature, "Hips"))
        print("Spine", find_bone(armature, "Spine"))
        print("Thumb 2.L", find_bone(armature, "Thumb 2.L"))
        print("Little Finger 2.L", find_bone(armature, "Little Finger 2.L"))

        return {"FINISHED"}


class NyaaToolsInitMods(Operator):
    """Creates my prefered modifier stacks"""
    bl_idname = "nyaa.init_mods"
    bl_label = "Initialize Modifier Stack"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = bpy.context.active_object

        if obj is None:
            self.report({"ERROR"}, "Expected a mesh object, got: None")
            return {"CANCELLED"}

        if obj.type != "MESH":
            self.report({"ERROR"}, "Expected a mesh object, got: " + obj.type)
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
        self.report({"INFO"}, "Merge & Export")
        print("\n\n")

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
                            mergeOntoTarget(meshLayerName, meshName, armature)
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
