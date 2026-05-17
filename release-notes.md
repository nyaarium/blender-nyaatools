## v2.5.0

### Features

- Added per-profile Forward/Up axis controls for FBX exports.

### Changes

- GLB Export: With "Pack Textures in GLB" off, GLB now exports geometry and material slots only, with no embedded textures.
- AO bake reworked using a `ShaderNodeAmbientOcclusion` to EMIT pipeline. Resolution floors to 512 when source textures are tiny.
- Pack mode bake now runs on duplicated meshes so originals retain their shape keys.
- Bake Channels panel hides when pack mode is on.
- `prepare_mesh`: rewires an existing Armature modifier instead of adding a new one.

### Fixes

- Merge & Export: Mesh and armature world transforms are now preserved through export. Raises and translations on the rig survive a round-trip.
- Fixed Edit Export Profile dialog clobbering saved values on open.

## v2.4.3

- Fixing some merge & export error handling

## v2.4.2

- Relaxed Fix Name requirements. Only checks if it's a real supported image extension.

## v2.4.1

Created a new operator to apply modifiers on objects with shape keys (closes #77)
- Uses UV projection to figure out where new vertices were meant to go.
- Works with modifiers like Decimate
- Requires a valid UV Map unwrap.
- If your unwrap is not so great, it will attempt some temporary best-effort UV fixes (temporarily, then remove em)
