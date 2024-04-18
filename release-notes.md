### Important Notes

> - Be sure to **restart Blender** after updating this addon. Not sure why it wont update without a restart. (issue #10)
>
> - Like most Blender operators, my buttons will open a **small panel** to the bottom left of your 3D viewport, where you can enter the settings. Expand it to configure settings.

### Release Notes

- Added new operator: **Merge Armatures** (closes #47)

  - Select 2 armatures. If one is an **Avatar**, it will be the armature base. Otherwise, make sure you actively `Ctrl + Click` your armature base last.

- Reduced the shapekey cleanup tolerance (fixes #49)

- For meshes named "Face", "Head", or "Body" _(when no "face" is present)_, skip cleanup of shapekeys named "vrc.\*" or "v\_\*" (closes #17)
