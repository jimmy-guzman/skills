## What

- `styles.css`: the `max-height: 320px` cap on `.ProseMirror img` is gone; an image draws at its own size up to the column, with `height: auto`. A 1440x900 screenshot drew at 512x320 before and at 624x390 now.
- The viewer:
  - `image-dialog.tsx`: the app's `Dialog` holding the image alone at `naturalWidth / devicePixelRatio`, bounded by the window less 2rem.
  - `editor.tsx`: opens it from an `open` button shown on hover, from the DOM `dblclick` (the selection drag suppresses the `mousedown` ProseMirror counts clicks with), or from ⌘⇧O with the image selected; Escape lands back on the selected image.
- The resize:
  - `image-resize.ts`: a node view with one handle on the right edge while the image is selected and loaded. Pointer capture, `stopPropagation` before `DragSelectionView` hears the press, width clamped to 64px and the line at the source, one transaction on release that keeps the selection. Only `width` is stored; a press that never moved or a `pointercancel` writes nothing.
  - `drag-selection.ts`: a press on a selected node that never moves leaves it selected.
- Width written as HTML (`D97`):
  - `image-tag.ts`: `imageTagAttrs` reads one `<img>` carrying only `src`, `alt`, `title` and a whole positive `width`; `imageTag` writes it with `outerHTML`.
  - `extensions.ts`: `NoteImage` owns an inline tokenizer for the tag and writes `<img src alt width>` once a width exists, `![alt](src)` otherwise; `height` leaves the schema; `NoteHardBreak` writes `\` after a sized image so the tag line cannot open an HTML block.
  - `html-literal.ts`: both nodes hand a recognized tag to the image node; any other `<img>` stays code.
  - `markdown.rs`: `is_image_tag` applies the same rule and `readable_text` drops such a tag from the search body.
  - `fixtures/image-tags.json`: the 20 cases both sides pass.
- Docs:
  - `SPEC.md`: the viewer, the resize, the tag exception to raw HTML, the search body, the still click on a selected image.
  - `DESIGN.md`: the handle and the open button.
  - `ARCHITECTURE.md`: the shared tag rule and the second syntax `NoteImage` owns.
  - `DECISIONS.md`: `D97`.
  - `README.md`: ⌘⇧O opens the selected image.

## Why

Closes #321.

A 1440x900 screenshot drew at 512x320, so the text in it was unreadable, and nothing opened an image bigger. Markdown has no size syntax, and the one form GitHub, Obsidian, VS Code and pandoc all draw at a given width is `<img width>`, so a resize writes that and nothing else.

If the tag rule is wrong, a note shows an `<img>` as an image in notras that another renderer shows differently, or a search hit lands on text the note never shows; the fixture holds the rule on both sides, and the signal is a tag that renders as code here or a search result with no visible match. If the handle's press leaks, the image moves instead of resizing; the editor-root listener test covers the press, and the signal is the D71 ghost appearing on a handle drag.
