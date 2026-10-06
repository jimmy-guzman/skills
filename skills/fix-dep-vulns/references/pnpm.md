# pnpm reference

Check the repo's pnpm version in the `packageManager` field. Headings match the italic names in `SKILL.md`.

**Version floors.**

- 11.0: `minimumReleaseAge` defaults to 1440 minutes; `pnpm` field in `package.json` is no longer read (`pnpm.overrides`, `patchedDependencies` must move to `pnpm-workspace.yaml`).
- 11.13: convergence overrides (`pkg@` selector).
- 11.16: `audit.ignore` in `pnpm-workspace.yaml` (older repos use the deprecated `auditConfig.ignoreGhsas`).
- 11.28 / 12.0: `audit.ignorePrune`.
- 12.4: ignored advisories reported separately.

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

On a stale lockfile, `pnpm update <pkg>` can still touch many unrelated entries — anything whose range now resolves to a newer release. The large diff isn't a bug; review it, but don't fight it with pinning.

`pnpm audit --fix=update` re-resolves every vulnerable package at once within existing ranges. Fine for a repo with many stale findings; plain `--fix` writes overrides instead and stays off limits.

## Overrides

Overrides live in `pnpm-workspace.yaml`. On pnpm 11+, `pnpm.overrides` in `package.json` is ignored (pnpm warns "The `pnpm` field in `package.json` is no longer read"); any entry there does nothing. Migrate it to `pnpm-workspace.yaml` or delete it. YAML allows comments, so every override should carry one.

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

Patched dependencies live under `patchedDependencies` in `pnpm-workspace.yaml`. On pnpm 11+, entries under `patchedDependencies` in `package.json` are ignored for the same reason as `pnpm.overrides`; migrate or delete them. To remove one:

```sh
pnpm patch-remove <pkg>@<version>
```

That removes the entry, deletes the patch file, and updates the lockfile. Patches apply to one exact version, so they have the same staleness problem as overrides.

## Dismissals

`audit.ignore` in `pnpm-workspace.yaml` takes GHSA ids. See Version floors for the setting floors.

```yaml
audit:
  ignore:
    # Dev-only, <pkg> via <parent>. Remove when <parent> ships <major>.
    - GHSA-xxxx-xxxx-xxxx
```

Set `audit.ignorePrune: true` so stale entries get removed by `pnpm audit --fix=update` once the advisory clears. Record the same note in the scanner's dismissal.

## Release age

`minimumReleaseAge` defaults to 1440 minutes on pnpm 11+. pnpm won't install a version until it's been published for a day. If the patched version is newer than that, `pnpm update` won't pick it up yet. Report it to the user. Don't lower the setting unless they ask.

`pnpm audit --fix=update` can add exceptions to `minimumReleaseAgeExclude` to pull a fresh fix past the release-age wait. That's a workaround that disables the protection the skill tells you not to lower. After any `--fix=update`, diff `pnpm-workspace.yaml` and revert any new `minimumReleaseAgeExclude` entry unless the user asked for it.
