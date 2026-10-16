Closes #321.

**Why.** Screenshots drew too small to read, and nothing opened them bigger. Markdown has no size syntax, so a resized image is saved as `<img src alt width>`, the one form GitHub, Obsidian, VS Code and pandoc all honor.

**Approach.** The 320px cap is gone; images draw at their own size up to the column width. An image opens full size from a hover button, double-click, or ⌘⇧O, and a drag handle resizes it; only `width` is saved. TS and Rust share the tag rule through `fixtures/image-tags.json` so search and render agree.

### Before

<!-- before --> 1440x900 screenshot at 512x320.

### After

<!-- after --> 1440x900 screenshot at 624x390.

**Review.** The tag rule lives twice, in `image-tag.ts` and `markdown.rs`. That is the part worth a close read.
