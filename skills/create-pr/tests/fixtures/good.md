## Why

Closes #321.

Screenshots drew too small to read, and nothing opened them bigger. Markdown has no size syntax, and `<img width>` is the one form GitHub, Obsidian, VS Code and pandoc all honor, so resizing writes that.

## What

- Images draw at their own size up to the column width; the 320px cap is gone.

  ### Before

  <!-- before --> 1440x900 screenshot at 512x320.

  ### After

  <!-- after --> 1440x900 screenshot at 624x390.

- `image-dialog.tsx`, `editor.tsx`: open an image full size from a hover button, double-click, or ⌘⇧O.
- `image-resize.ts`: drag a handle on the selected image to resize it; only `width` is saved.
- Sized images save as `<img src alt width>` (D97). TS and Rust share one rule, held by `fixtures/image-tags.json`.
- Docs: spec, design, architecture, decisions, README.
