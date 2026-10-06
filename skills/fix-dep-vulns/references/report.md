# Report templates

## Triage summary

Use this after verifying. Keep each line short. Leave out sections with nothing in them.

```markdown
## Vulnerability triage

`<audit command>`: <before> findings -> <after> findings

| Package | Severity | Path | Fix | Result |
| --- | --- | --- | --- | --- |
| `<pkg>` | high | `<parent>` (prod) | Refreshed lockfile | 1.2.0 -> 1.2.5 |
| `<pkg>` | moderate | `<parent>` (dev) | Dismissed | Requires major |

### Fixed

- `<pkg>` 1.2.0 -> 1.2.5. `<parent>` already allowed `^1.2.0`, so the lockfile was stale.
- `<pkg>` gone. `<parent>` <old> -> <new> dropped the dependency.

### Not fixed

- `<pkg>` via `<parent>`. Dev-only. Fix requires `<parent>` <major>. Dismissal note below.

### Overrides and constraints

- Removed `<selector>`. Parents now allow the patched version.
- Added `<selector>`. <reason>. Remove when <condition>.

### Verified

- <audit and trace commands>, with the packages checked
- <type-check, lint, test, build scripts that ran>

### Smoke test

- <screens or features powered by any upgraded production parent>
```

## Dismissal note

For the scanner's dismissal comment. One per finding.

```markdown
Not exploitable. `<pkg>` comes from `<parent>`, which is <dev-only / a build-time tool / a Node tool that never runs in the browser>. <Advisory precondition, and one sentence on why this repo can't meet it in production, build, or CI.> Fix requires a major bump of `<parent>`, tracked in <ticket>.
```

Examples:

> Not exploitable. `vue-template-compiler` comes from `vue-tsc` 1.8 and is only used for type-checking. It never ships to the browser. No patched 2.x will exist. Fixed by the `vue-tsc` upgrade, tracked in <ticket>.

> Not exploitable. `image-size` comes from `texture-compressor`, a Node tool for encoding textures that never runs in the browser. Fix requires a major bump, tracked in <ticket>.
