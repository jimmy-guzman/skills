# pnpm reference

Check the repo's pnpm version in the `packageManager` field. Notes below name the release that introduced each setting.

Headings match the italic names in `SKILL.md`.

## Contents

- Investigating
- Fixing
- Overrides
- Patches
- Dismissals
- Release age

## Investigating

```sh
pnpm audit                                      # all findings
pnpm audit --audit-level high                   # high and critical only
pnpm why -r <pkg>                               # every path that pulls <pkg> in, across all workspace packages
pnpm view <pkg>@<version> dependencies.<dep>    # range a specific version declares
pnpm view <pkg>@latest dependencies.<dep>       # range the latest version declares
pnpm view <pkg> version                         # latest version
pnpm view <pkg> dist-tags                       # latest, next, legacy, and so on
pnpm view <pkg> versions --json                 # every published version
```

`pnpm view` prints nothing for a field that doesn't exist. Before reading empty `dependencies.<dep>` output as "no longer depends on it", check `optionalDependencies.<dep>` and `peerDependencies.<dep>` too.

Checking what the code actually imports, before removing a parent:

```sh
grep -rn "<pkg>[/'\"]" --exclude-dir=node_modules --exclude=pnpm-lock.yaml .
```

That pattern catches static imports, dynamic `import()`, `require`, and side-effect imports, including subpath imports like `<pkg>/sub`, in source, tests, and config.

## Fixing

```sh
pnpm update <pkg>                 # re-resolve <pkg> within existing ranges, including transitive copies
pnpm update "<scope>/*"           # same, for a whole scope
pnpm add <parent>@^<version>      # upgrade a direct dependency
pnpm remove <parent>              # remove a direct dependency
pnpm dedupe                       # collapse duplicate copies where ranges allow
```

If `pnpm update <pkg>` reports "Already up to date" but the finding stays, a parent pins an exact version or its range excludes the fix. Move to upgrading the parent.

`pnpm audit --fix=update` re-resolves every vulnerable package at once within existing ranges. Fine for a repo with many stale findings; plain `--fix` writes overrides instead and stays off limits.

## Overrides

Overrides live in `pnpm-workspace.yaml`. Older repos may still have them under `pnpm.overrides` in `package.json`. YAML allows comments, so every override should carry one.

```yaml
overrides:
  # Reason: <advisory>, pinned exact by <parent>@<version>.
  # Remove when: <parent> ships a release with <pkg> >= <fixed>.
  "<parent>><pkg>": ^<fixed>
```

Selector syntax:

| Selector | Applies to |
| --- | --- |
| `pkg` | every copy of `pkg` |
| `pkg@<1.2.3` | copies resolved below 1.2.3 |
| `parent>pkg` | `pkg` only when `parent` depends on it |
| `parent@1>pkg` | `pkg` only under `parent` 1.x |
| `pkg@` | convergence override, see below |

Setting a value to `-` removes the dependency entirely.

### Convergence overrides

Available since pnpm 11.13. An empty range, `pkg@`, rewrites a dependency only when the new version satisfies the range that dependency declared:

```yaml
overrides:
  "<pkg>@": <exact-version>
```

A parent asking for `^1.2.0` converges on the override. A parent asking for `^0.9.0` keeps its own resolution. It never forces a major. When every declared range allows something newer, pnpm warns that the override is stale and names the version to converge on.

Limits: the value must be an exact version, and it can't be combined with a parent selector.

Use this instead of a plain override when the goal is a security floor and the parents' ranges already allow the patched version.

## Patches

Patched dependencies live under `patchedDependencies` in `pnpm-workspace.yaml` or `package.json`. To remove one:

```sh
pnpm patch-remove <pkg>@<version>
```

That removes the entry, deletes the patch file, and updates the lockfile. Patches apply to one exact version, so they have the same staleness problem as overrides.

## Dismissals

`audit.ignore` in `pnpm-workspace.yaml` takes GHSA ids (since 11.16; older repos use the deprecated `auditConfig.ignoreGhsas`). Ignored advisories are reported separately since 12.4.

```yaml
audit:
  ignore:
    # Dev-only, <pkg> via <parent>. Remove when <parent> ships <major>.
    - GHSA-xxxx-xxxx-xxxx
```

Set `audit.ignorePrune: true` so stale entries get removed by `pnpm audit --fix=update` once the advisory clears. Record the same note in the scanner's dismissal.

## Release age

Since pnpm 11, `minimumReleaseAge` defaults to 1440 minutes. pnpm won't install a version until it's been published for a day. If the patched version is newer than that, `pnpm update` won't pick it up yet. Report it to the user. Don't lower the setting unless they ask.
