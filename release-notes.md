### Important Notes

> Be sure to **restart Blender** after updating this addon.

### Release Notes

Improved the **Bake Material Slots** optimizer

- Now analyzes your texture for variance in details and tries another optimization.

- Automatic downsizing: It uses the lowest resolution possible that wont harm the quality. Very safe.

- Textures with fairly simple colored islands will see the best improvements. Metallic maps, smoothness/roughness, etc. If it's just a single color, you will see it downscale all the way down to 8x8.
