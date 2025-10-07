### Important Notes

> - Be sure to **restart Blender** after updating this addon. Not sure why it wont update without a restart. (issue #10)
>
> - Like most Blender operators, my buttons will open a **small panel** to the bottom left of your 3D viewport, where you can enter the settings. Expand it to configure settings.

### Release Notes

Added **Merge & Export** target for `.obj` files and **Voices of the Void**.

**Voices of the Void Exporting:**

When setting up the avatar, set the **Export path** to your Voices `printers` folder. Like:
> `C:\Users\nyaarium\AppData\Local\VotV\Assets\meshes\printer\`

It will automatically create the folder and name the export properly:

- **Avatar name** you chose will be sanitized for windows paths. 
Both folder and `.obj` file will be named the **sanitized avatar name** for proper VotV detection.

- A default `properties.cfg` template will be placed there for you.

Once your avi is configured, and the export path points to a directory, an export profile for Voices will appear.

---

**Collision handling:**

It will error at you if you dont make at least 1 `UCX_` simplified collision mesh.

If you need to make a concave shape **like a box**, you cannot make a `UCX_` out of 1 mesh. It must be formed of multiple meshes to make the walls and bottom. [See this guide for a better explaination](https://github.com/madrod228/voicesoftheprinter/blob/main/Guide-VOTV%20Printer.md#colliders)

For example, to model a cardboard box's collider, you might make 7 flat squares and name them:
- `UCX_box_side_left`
- `UCX_box_side_right`
- `UCX_box_side_front`
- `UCX_box_side_back`
- `UCX_box_bottom`
- `UCX_box_flap_left`
- `UCX_box_flap_right`

---

⚠️ **Important:** My workflow assumes you fully utilize Blender shader nodes. Keep reading for technical details.


**Shader node tree search:** It will follow the **Material Output** back to a **Principled BSDF** and try to read the input sockets for:

- Base Color
- Alpha
- Metallic
- Roughness
- Specular IOR
- Emission Color

**Unused sockets and handling:**

If there are no sockets connected, it will default it to an 8x8 px image to suppress the in-game printer warnings.

If there are textures anywhere on the chain of a socket, it will choose the largest resolution of found textures. *(defaults to 512x512, if purely node generated fx)*

**Socket auto-baking and optimization:**

It will bake the sockets, auto pack them, and perform a quick optimization for bakes of just a solid color.

- **Connected sockets** will render a bake (with Cycles).
- **Unused sockets** create a quick 8x8 image.
- The results of these bakes are auto-packed:
    - Color + Alpha
    - Metallic + Specular IOR + Roughness
- A complex color scanning pass occurs after a bake to determine if it "looks like" a fully solid color image. If so,
    - It will demote the image resolution down to 8x8 and assign it the used color. 🪲
	- **Use case:** Helps with a lot of substance painter art where they dont use any PBR channels, but export the full 8192x8192 black square anyways.

🪲 Submit an issue right away if you see it demoting your maps despite there being some details. I'm still refining the algorithm to not destroy your processor, but give decent optimizations.

**Image placements:**

Will use the multi-material method of naming your textures. This means you can have multiple material slots for your model.

Assuming one of the material slots was named **"Barycentric Test"**, it will sanitize before export, and name the images for this slot:

- diffuse_Barycentric_Test.png
- emissive_Barycentric_Test.png
- normal_Barycentric_Test.png
- pbr_Barycentric_Test.png
