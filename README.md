# NyaaTools

NyaaTools is a bundle of handy tools designed for avatar/assets creators who need tools for mesh preparation, material baking of complex shader trees, and multi-format exports. A lot of work was put into intelligent shader nodes and image analysis algorithms to optimize the exports.

Location: **N-Panel** > **NyaaTools**

## Asset Management

Designed entirely around non-destructive workflows, modifiers are applied on the exported objects and not on the source meshes. You do NOT have to destructively apply before export. The addon is designed to aid in non-destructive workflows.

**Asset types** - Assets support both rigged characters (armature-hosted) and static meshes (mesh-hosted). When creating an asset:
- **Rigged assets**: Config lives on the Armature object - select the armature to see the asset
- **Static assets**: Config lives on a Mesh object - select the mesh to see the asset
- Can also export posed characters/props by applying the armature _(Export as Static option)_

**Layers** - Group meshes by purpose _(Base, Outfit, Hair, etc.)_ and instruct the exporter to merge them together on export. Each mesh is assigned to a layer, and all meshes in the same layer are merged into one during export. The special `UCX` layer is reserved for Unreal Engine collision meshes, and only export if you check it on the export profile for Unreal Engine.

**Export profiles** - Configure multiple targets to quickly export directly into Unity `Assets/` folder. Quickly switch between different destinations and engine-specific settings:
- **Formats**:
  - FBX _(Unity/Unreal)_
  - OBJ _(static meshes)_
  - [VotV 0.9 _(Voices of the Void)_](https://github.com/madrod228/voicesoftheprinter/blob/main/Guide-VOTV%20Printer.md)
- **Static export**: Apply pose and modifiers, remove armature - exports rigged character as static mesh
- **UE Colliders**: Toggle to include/exclude UCX_ collision meshes per profile
- **Bake after export**: Auto-trigger material baking after successful export

## Material Baking

**Smart Baking** - Automatically analyzes complex shader trees to configure bake passes. Supports procedural materials, nested node groups, and requires at least 1 Principled BSDF to sample from.

**Optimization** - Intelligent mipmap-degradation analysis to reduce texture resolution on images where high detail isn't needed.
- **Analysis**: Scans baked images' **UV islands** to see what would be degraded if downsampled.
- **Downscaling**: Where possible, reduces resolution _(min 8x8)_ for maps with low frequency detail _(uniform metallic/roughness)_.

**Texture Packing** - Configure custom channel-packing for your specific engine needs.
- Map any source _(R, G, B, Alpha, Normal GL/DX, Metallic, Roughness, Emission, etc.)_ to output images.
- Even supports silly games like [**Kenshi**](https://kenshi.fandom.com/wiki/Custom_Character_Race_and_Normal_Map_(displacement_map)), where the **normal map's** RGBA is defined as `nd-nd-nd-nx`:

  | Channel | Direction | Code |
  | --- | --- | --- |
  | **Red** | `-Y` | `nd` |
  | **Green** | `-Y` | `nd` |
  | **Blue** | `-Y` | `nd` |
  | **Alpha** | `X` | `nx` |

**Presets** - Standard configuration profiles included:
- **PBR (MRS)**: Generic packing Metallic, Roughness, Specular into `me-ro-sp`. Change as you need.
- **Poiyomi**: Geared for VRChat, packing Metallic, Smoothness, and value 1 into `me-sm-1`
- **VotV**: Voices of the Void specific packing `[me-sp-ro]`.
  - All 4 maps are set to suppress the "missing texture" warning.
  - Unused textures are set to 8x8 pixels for minimal performance impact.

**Formats** - Choose the right format for your data:
- **PNG**: 8-bit, best for anything about "color".
- **EXR**: 32-bit linear, highly recommended for Utility maps _(Normal, PBR, etc)_ to preserve exact data values and neutral points.

## Other Handy Tools

**Mesh Cleanup** - Selection-based batch tools for removing unused materials, shape keys, and vertex groups.

**Armature Tools** - **Dissolve bones** merges a selected series of bones and combines their vertex groups (blending weights). Good for reducing hair bone counts on VRChat avatars.

**Image Packer** - Quickly pack or unpack all images associated with selected objects into the Blender file.

