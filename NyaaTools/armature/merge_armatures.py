import bpy
from .list_bone_merge_conflicts import list_bone_merge_conflicts


# Example usage
# target_armature = bpy.data.objects.get('Armature')
# extra_armature = bpy.data.objects.get('Armature.001')
# orphan_parent_map = {
#     'Hair Root': 'Head',
#     'Ribbon': 'Chest'
# }
# merge_armatures(target_armature, extra_armature, orphan_parent_map)

def merge_armatures(target_armature, extra_armature, orphan_parent_map):
    """
    Merge two armatures, re-parenting the specified orphan bones.
    """
    def merge_move_objects(target_armature, extra_armature):
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        extra_armature.select_set(True)
        bpy.context.view_layer.objects.active = extra_armature
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.ops.object.select_all(action='DESELECT')
        
        for obj in bpy.data.objects:
            if obj.parent == extra_armature:
                obj.parent = target_armature
                obj.matrix_world = extra_armature.matrix_world.inverted() @ obj.matrix_world

                # Select for transform apply
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                print(f"Moving from  {extra_armature.name} -> {target_armature.name}:  {obj.name}")

        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.ops.object.select_all(action='DESELECT')


    def get_bone_parenting(target_armature, extra_armature):
        """
        Get the original parenting of bones in the extra armature.
        """
        target_bone_names = {bone.name for bone in target_armature.data.bones}  # Set of bone names in target armature
        original_parents = {}
        for bone in extra_armature.data.bones:
            if bone.name not in target_bone_names and bone.parent:
                original_parents[bone.name] = bone.parent.name

        return original_parents


    def delete_conflict_bones(armature, conflicts):
        """
        Delete bones in the extra armature that are in conflict.
        """
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='EDIT')

        edit_bones = armature.data.edit_bones
        for bone_name in conflicts:
            if bone_name in edit_bones:
                print(f"Deleting duplicate bone:  {armature.name} -> {bone_name}")
                edit_bones.remove(edit_bones[bone_name])
        bpy.ops.object.mode_set(mode='OBJECT')


    def restore_bone_parenting(armature, original_parents):
        """
        Restore parenting of now the now parentless bones (because of the merge)
        """
        bpy.ops.object.mode_set(mode='OBJECT')
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='EDIT')
        
        for bone in armature.data.edit_bones:
            # Only if it's orphaned as a result of merge
            if bone.parent is None and bone.name in original_parents:
                new_parent_name = original_parents[bone.name]
                print(f"Reparenting:  {bone.name} -> {new_parent_name}")
                bone.parent = armature.data.edit_bones[new_parent_name]


    def apply_orphan_bone_parenting(armature, orphan_parent_map={}):
        """
        Apply new parenting relationships for specified orphan bones according to a given mapping.
        """
        bpy.ops.object.mode_set(mode='OBJECT')
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='EDIT')

        edit_bones = armature.data.edit_bones

        for orphan, new_parent_bone in orphan_parent_map.items():
            if orphan in edit_bones:
                orphan_bone = edit_bones[orphan]
                if new_parent_bone in edit_bones:
                    orphan_bone.parent = edit_bones[new_parent_bone]
                    print(f"Re-parented to  {new_parent_bone}:  {orphan}")
                else:
                    print(f"Warning: New parent bone {new_parent_bone} not found for {orphan}.")
            else:
                print(f"Warning: Orphan bone {orphan} not found in the merged armature.")

        bpy.ops.object.mode_set(mode='OBJECT')


    ######################################
    
    
    # Step 1: Move objects from extra armature to target armature
    merge_move_objects(target_armature, extra_armature)

    # Step 2: Remember original bone parenting
    original_bone_parents = get_bone_parenting(target_armature, extra_armature)
    print("Original bone parenting:", original_bone_parents)
    
    # Step 3: Delete all the conflict bones
    conflicts = list_bone_merge_conflicts(target_armature, extra_armature)
    delete_conflict_bones(extra_armature, conflicts)

    # Step 4: Join the armatures
    bpy.ops.object.select_all(action='DESELECT')
    target_armature.select_set(True)
    extra_armature.select_set(True)
    bpy.context.view_layer.objects.active = target_armature
    bpy.ops.object.join()
    bpy.ops.object.select_all(action='DESELECT')
    
    # Step 5: Recall the original parenting and restore it
    restore_bone_parenting(target_armature, original_bone_parents)
    
    # Step 6: Apply the parents for orphans described by `orphan_parent_map`
    apply_orphan_bone_parenting(target_armature, orphan_parent_map)
