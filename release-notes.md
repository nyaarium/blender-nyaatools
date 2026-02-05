## v2.4.1

Created a new operator to apply modifiers on objects with shape keys (closes #77)
- Uses UV projection to figure out where new vertices were meant to go.
- Works with modifiers like Decimate
- Requires a valid UV Map unwrap.
- If your unwrap is not so great, it will attempt some temporary best-effort UV fixes (temporarily, then remove em)
