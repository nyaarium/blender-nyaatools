## 🎊 Happy New Year! v2.x 🎊

Finally, a fix to hot-reload of the addon when you update. (#10)

⚠️ **This will be the final time** you need to **restart Blender** after updating. In the future, you will only need to disable/enable the addon to restore your settings and reload the changes.

---

### Full Rewrite

This is a full rewrite for a new UI experience and new Asset management system. (#13, #14, #43, #44, #70)

Thanks Claude Opus!

---

### **New UI Experience**

The interface has been completely overhauled for a cleaner, more intuitive workflow:
- **Organized Asset Lists**: Managing avatars/assets with many meshes is now much easier.
- **Focused Settings**: Instead of a wall of settings in your sidebar, I've moved configuration into popup windows.
- **Progress Sceen**: A new progress screen shows you the tasks it is doing during **Merge & Export** and **Bake**.

---

### **Unified Asset System**

**Avatars** are now simply **Assets**, giving you more options of exporting non-armatured assets.

- **Export Profiles**: Create different export settings for different projects. You can configure things per profile depending on where you are exporting to.
  - **Unreal Engine** - You can check on "Include Colliders" to export `UCX_` meshes with this export profile.
  - **Voices of the Void** - It will export with exact naming conventions as required by the game (`0.9`).
- **Layer Management**: More control over assigning meshes to layers.
- **Static Assets**: Before, you could only export rigged avatars (for VRChat / VRM users). Now, you can configure static meshes as Assets, or even pose your character and have it export as static (applies pose and removes armature).

---

### **Baking Pipeline**

Baking was sort of experimental, made only to export to Voices of the Void before. But now it is fully configurable:
- **Smart Material Baking**: The tool follows the shader nodes inside your material to automatically configure the bake, even in complex setups where your Principled BSDF is hidden within nested **Groups**.
  - Requires a **Principled BSDF** to be present somewhere in the material tree.
  - Procedural materials that are composed of complex nodes are supported.
  - Best-resolution can be automatically determined (if you leave "Optimize" checked). Just set the maximum resolution.
  - "Optimize" checkmark also uses a mipmapping algorithm I wrote to determine if the texture resolution can be dropped down (minimum 8x8).
- **Custom Texture Packing**: You can fully configure what utility map is in which channel.
  - _Example:_ **Kenshi** for instance, you would set the normal map to be:
    - **Red**: Normal -Y (`nd`)
    - **Green**: Normal -Y (`nd`)
    - **Blue**: Normal -Y (`nd`)
    - **Alpha**: Normal X (`nx`)
- **Texture Packing Presets**: Pre-configured settings of Color, Normal, PBR, and Emission:
  - **PBR (MRS)**: PBR channels set to `me-ro-sp`
  - **Poiyomi**: PBR channels set to `me-sm-1`
  - **Voices of the Void (VotV 0.9)**: PBR channels set to `me-sp-ro`

---

*(re-released and deleted 2.0.0, since it had major regressions)*
