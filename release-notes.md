### Important Notes

> - Be sure to **restart Blender** after updating this addon. Not sure why it wont update without a restart. (issue #10)
>
> - Like most Blender operators, my buttons will open a **small panel** to the bottom left of your 3D viewport, where you can enter the settings. Expand it to configure settings.

### Release Notes

- Merge & Export now skips applying the "MToon Outline" modifier in prep for VRM avatars

- Merge & Export now keeps **EMPTY**s that are in use, in prep for VRM avatar exporting

- Merge & Export now finishes up by recursive pruning unused data

- Merge and Export removes UV Maps beginning with "--"

- Added "Dissolve Bones" button. Good for reducing hair bones down (#25)

- Added a "Select Standard Bones" button

_Nyaa's Normalization:_

- Roll normalization now optional. Defaults to true. (#24, #42)

- Changed bone rolls to better represent rotation on the joints.
