# gitzy

Optional commit-message tool for `commit`. Read Gotchas before running anything.

## Contents

- Gotchas
- Flags
- Config detection
- commitlint handoff
- Defaults
- JSON schema

## Gotchas

- **gitzy is optional, never a blocker.** Treat any non-zero exit, timeout, or missing `npx` as "not available" and fall back to writing the message by hand (see `commit`'s step 5). Don't prompt the user to install anything, don't retry.
- **Always `npx -y gitzy ...`.** Skips the one-time package-install confirmation, which has no TTY to answer in an agent session.
- **Always preview with `--dry-run --json` first.** Run the exact commit invocation with `--dry-run --json` appended during the confirmation step, parse `.header` from the JSON, and show that literal string to the user before committing anything.
- **`--retry` after a hook rejection.** Reuses the last answers and skips prompts; faster than rebuilding every flag.
- **`--amend` pre-fills from HEAD.** Don't manually pass `--type`/`--subject` when amending unless the user wants them changed.
- **`--stdin` for anything not covered by a flag.** Reads a JSON object of answers from stdin; CLI flags still take priority over stdin values if both are given.

## Flags

### `gitzy commit`

| Flag | Alias | Purpose |
|---|---|---|
| `--type <type>` | | Set type inline |
| `--scope <scope>` | | Set scope inline |
| `--subject <subject>` | `-m` | Set subject inline; with `--type` skips all prompts |
| `--body <body>` | | Set body inline |
| `--breaking [breaking]` | | Mark as breaking; message used for `footer`/`both` formats |
| `--issue <issue...>` | | Set issues inline, repeatable |
| `--dry-run` | `-D` | Show the commit message without committing |
| `--retry` | | Retry last commit, skip prompts |
| `--amend` | `-a` | Amend previous commit; pre-fills from HEAD |
| `--no-verify` | `-n` | Skip git hooks |
| `--json` | | Structured JSON output |
| `--no-emoji` | | Disable emoji in the message |
| `--co-author <coAuthor...>` | | Add co-authors, repeatable |
| `--signoff [signoff]` | `-s` | Add a `Signed-off-by` trailer |
| `--hook` | | Enable running inside a git hook |
| `--stdin` | | Read answers from stdin as JSON |

## Config detection

Resolution order, first hit wins:

1. A `gitzy` key in `package.json`.
2. `.gitzyrc`, `.gitzyrc.json`, `.gitzyrc.js`, `.gitzyrc.cjs`, `.gitzyrc.mjs`.
3. `gitzy.config.js`, `gitzy.config.cjs`, `gitzy.config.mjs`, `gitzy.config.ts`, `gitzy.config.mts`.
4. Any of the above under a `.config/` directory.

TypeScript config (`gitzy.config.ts`/`.mts`) requires Node 22.12.0 or newer.

Main configurable fields: `types`, `scopes`, `prompts`, `header.{max,min}`, `body.{max,min}`, `breaking.format` (`footer`, `!`, or `both`), `emoji.{enabled,breaking,issues}`, `issues.{pattern,prefix,hint}`.

## commitlint handoff

gitzy auto-detects a local commitlint config and merges its own rules over it; gitzy's values win on conflict. Run `npx -y gitzy config` to inspect the fully resolved configuration if a type/scope enum or header limit needs confirming before drafting.

## Defaults

- **Emoji**: enabled, placed right after the colon (`feat: ✨ add dark mode`). Disable with `--no-emoji`, `GITZY_NO_EMOJI`, or `emoji.enabled: false` in config.
- **Scope**: optional, omitted from the header if empty.
- **Breaking format**: `footer` by default (`BREAKING CHANGE: <description>`); alternatives are `!` after the type, or `both`.
- **Issues footer**: `{prefix} {issue}`, for example `closes #123`.
- **Header length**: max 50, min 5.
- **Body length**: max 70, min 5.

## JSON schema

`gitzy commit --json --dry-run` (or without `--dry-run`, after committing) prints:

```json
{
  "header": "feat: ✨ add dark mode",
  "body": "",
  "footer": "",
  "message": "feat: ✨ add dark mode",
  "parts": {
    "type": "feat",
    "scope": "",
    "subject": "add dark mode",
    "body": "",
    "breaking": "",
    "issues": [],
    "coAuthors": [],
    "signoff": false
  }
}
```

Use `.header` directly in the `commit` skill's confirmation block.

Branch generation (`gitzy branch`) is a separate command with its own flags and is out of scope for this skill; `commit` only drives `gitzy commit`.
