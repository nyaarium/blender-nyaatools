### Important Notes

> Be sure to **restart Blender** after updating this addon.

### Release Notes

Added **Bake Material Slots** - a universal texture baker adapted from my previous Voices of the Void exporter.

**How it works:**

Select an object and click **Bake Material Slots**. It will:

1. Bake all Principled BSDF sockets to textures using Cycles
2. Auto-detect resolution from existing textures in the node tree
3. Pack channels into standard game-ready maps
4. Save to `textures/` folder (next to your blend file, or avatar export path if configured)

**Output files:**

File are labeled clearly so you know what channel does what.

- `Material Name.baked.rgba.png` - Base Color + Alpha
- `Material Name.baked.me-sp-ro.png` - Metallic + Specular IOR + Roughness
- `Material Name.baked.normalgl.png` - Normal map (OpenGL)
- `Material Name.baked.emission.png` - Emission Color

**Features:**

- Works with fancy shader node trees
- Untextured sockets bake at either 8x8 or 512x512, depending on if there was activity in the histogram
- Non-destructive. Will copy your mesh and mats to a new temp scene, instead of messing with your default scene.

**Notes:**

- Materials must be properly named (not "Material.001")
- Object needs at least one material slot
