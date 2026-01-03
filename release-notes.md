## 🎊 Happy New Year! v2.0 🎊

Finally, a fix to hot-reload of the addon when you update. (#10)

⚠️ **This will be the final time** you need to **restart Blender** after updating. In the future, you will only need to disable/enable the addon to reload the changes.

---

### Full Rewrite

This is a full rewrite for a new UI experience and new Asset management system. (#13, #14, #43, #44, #70)

Thanks Claude Opus!

---

### **New UI**

New panels, modals, tables/lists, selection boxes, etc. The experience will be a lot cleaner.


### **Assets**

**Avatars** are now known as **Assets** *(with a humanoid armature)*.

More generically, **Assets** may or may not have an armature. Meaning you can now use this to configure static props, or props with a non-humanoid armature.

Assets can now define multiple export profiles, so you can quickly switch between exporting to your Unity avi project, or somewhere else (like straight to Voices of the Void game).

This is a one-way upgrade from NyaaTools 1. There will be a migrate button when you click on an old avatar.

### **Baking**

Baking now features profiles as well, so you can custom define what maps you want exported. Presets for **PBR (MRS)**, **Poiyomi**, **Voices of the Void** are included.

It now also shows a progress window, so you can see where it's at.
