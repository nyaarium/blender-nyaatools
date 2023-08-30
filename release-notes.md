### Important Notes

> - Be sure to **restart Blender** after updating this addon. Not sure why it wont update without a restart. (issue #10)
>
> - Like much of other Blender operators, most of my buttons will open a **small panel** to the bottom left of your 3D viewport, where you can enter the settings.

### Release Notes

- Added "Dissolve Bones" button. Good for reducing hair bones down (#25)

- Added a "Select Standard Bones" button

- "Apply Top Modifier" now runs it for all selected meshes

- Added an Outline modifier button. ⚠️ Suitable for renders, not game exports.

- Fixed a bad Merge & Export bug where armature would be deleted if you started in Pose Mode (#19)

- Fixed some bugs related to hidden collections (#19, #27)

- Improved path handling for Export:

  - Handles either slashes
  - Can omit directory or filename. Both `D:/My Stuff` and `Avatar.fbx` are valid paths.
  - Absolute paths: `D:/My stuff`
  - Network paths: `\\wsl$\Ubuntu\home\nyaarium\my-stuff`
  - Relative path: `../../Unity/Assets/Avatar/avatar.fbx`

_Nyaa's Normalization:_

- Greatly improved breast detection, and all bone detection in general (#18)

- Roll normalization now optional. Defaults to false. (#24)

- Changed bone rolls to better represent rotation on the joints.
