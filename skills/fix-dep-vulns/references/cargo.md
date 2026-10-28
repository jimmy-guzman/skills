# Cargo reference

Covers Rust projects with a `Cargo.lock`. Headings match the italic names in `SKILL.md`. Run commands from the workspace root: one `Cargo.lock` covers every member.

**Version floors.**

- Cargo 1.62: `cargo add`. 1.66: `cargo remove`. 1.82: `cargo info`.
- Cargo 1.84: MSRV-aware resolver (`resolver = "3"`, default on edition 2024). See _Release age_.

Check `cargo --version`, and `rust-version` in `Cargo.toml` and `rust-toolchain.toml` if set. `cargo audit` is a separate install: `cargo install cargo-audit --locked`.

## Contents

- Investigating
- Fixing
- Overrides
- Dismissals
- Release age

## Investigating

```sh
cargo audit                                    # findings from Cargo.lock, against the RustSec database
cargo audit --json                             # same, machine-readable
cargo tree -i <pkg> --target all               # every path that pulls <pkg> in, on every platform
cargo tree -i <pkg>@<ver> --target all         # when the lockfile holds several versions of <pkg>
cargo tree -i <pkg> -e no-dev --target all     # drop dev-dependencies; build-dependencies still show
cargo tree -i <pkg> -e features --target all   # which feature of the parent turns <pkg> on
cargo tree -d                                  # crates locked at more than one version
```

`cargo audit` reads the whole lockfile: every target, every feature, dev and build dependencies included. `cargo tree` defaults to the host platform only, so without `--target all` a Windows-only or wasm-only path looks like it doesn't exist. Record which target and feature a path needs; that's often the dismissal evidence.

`cargo audit` reports vulnerabilities as errors and `unmaintained`, `unsound`, and `yanked` as warnings. Warnings have no patched version. The fix is replacing the crate or upgrading the parent that pulls it in, not a lockfile refresh.

For what a specific release declares, use the crates.io API. It rejects requests without a `User-Agent`:

```sh
curl -s -A "fix-dep-vulns" https://crates.io/api/v1/crates/<parent>/<version>/dependencies \
  | jq -r '.dependencies[] | select(.crate_id=="<pkg>") | "\(.req) \(.kind) optional=\(.optional) target=\(.target)"'
curl -s -A "fix-dep-vulns" https://crates.io/api/v1/crates/<pkg> | jq -r '.crate.max_stable_version'   # latest
```

Requirements are caret by default: `0.4` means `^0.4`, so `>=0.4.0, <0.5.0`. Below 1.0 every minor is a major.

Checking what the code uses, before removing a parent:

```sh
grep -rnE "\b<crate_name>::|extern crate <crate_name>" --include='*.rs' .
```

Hyphens become underscores in code (`serde-json` is `serde_json`), and `Cargo.toml` can rename a dependency (`foo = { package = "bar" }`), in which case code uses `foo`. Macro-only crates may show up only as `#[derive(...)]` or attribute macros; grep for the macro names too.

## Fixing

```sh
cargo update -p <pkg>                          # re-resolve <pkg> within existing requirements
cargo update -p <pkg>@<ver>                    # one copy, when several versions are locked
cargo update -p <pkg> --precise <fixed>        # to a specific version, if requirements allow it
cargo add <parent>@<version>                   # upgrade a direct dependency (add -p <member> in a workspace)
cargo remove <parent>                          # remove a direct dependency
```

If `cargo update -p <pkg>` says `Locking 0 packages`, a requirement excludes the fix (`--verbose` names what's held back). Move to upgrading the parent. If it prints `(available: v<x>, requires Rust <y>)`, see _Release age_.

An exact pin in the repo's own `Cargo.toml` (`= "1.2.3"`) blocks the update like a parent pin does. Relax it to a caret requirement at or above the fix.

If the repo vendors dependencies (`vendor/` plus a `[source]` replacement in `.cargo/config.toml`), re-run `cargo vendor` after any lockfile change, or the build keeps using the old source.

Libraries: downstream crates ignore this repo's `Cargo.lock`. A lockfile refresh fixes CI and the repo's own binaries. To protect consumers, also raise the requirement in `Cargo.toml` to the fixed version.

## Overrides

Cargo has no range override. Its escape hatch is `[patch]`, which swaps the source of a crate for the whole graph. It belongs in the workspace root `Cargo.toml`; Cargo ignores `[patch]` in member manifests. `.cargo/config.toml` can also hold `[patch]`; check there when listing existing overrides. `[replace]` is the deprecated predecessor; flag it for migration to `[patch]` or removal.

Use it when no fixed release exists yet but a fix has landed upstream or in a fork:

```toml
[patch.crates-io]
# Reason: <advisory>, no release with the fix yet.
# Remove when: <pkg> <fixed> is published to crates.io.
<pkg> = { git = "https://github.com/<owner>/<pkg>", rev = "<sha>" }
```

`[patch]` can't be scoped to one parent. It also can't cross a declared requirement: if the patched version doesn't satisfy what parents ask for, Cargo skips it with "Patch `<pkg>` was not used in the crate graph". Check for that warning after every `cargo update`.

Cargo allows one copy per semver-compatible range, so "breaks if installed more than once" usually means two majors are locked. Fix that by upgrading the parent on the old major, not with `[patch]`.

## Dismissals

`cargo audit` reads `.cargo/audit.toml` at the workspace root. It has no auto-expiring form, so write the removal condition in the comment. Use the RUSTSEC id.

```toml
[advisories]
ignore = [
  # Dev-only, <pkg> via <parent>. Remove when <parent> ships <major>.
  "RUSTSEC-xxxx-xxxx",
]
```

If the repo uses cargo-deny instead (`deny.toml`), the entry takes a reason:

```toml
[advisories]
ignore = [
  { id = "RUSTSEC-xxxx-xxxx", reason = "Dev-only, <pkg> via <parent>. Remove when <parent> ships <major>." },
]
```

Record the same note in the scanner's dismissal.

## Release age

Cargo has no release-age delay. The MSRV-aware resolver plays the same role in practice: with `resolver = "3"` (or `incompatible-rust-versions = "fallback"` under `[resolver]` in `.cargo/config.toml`), `cargo update` skips releases whose `rust-version` is newer than the package's, and prints `(available: v<x>, requires Rust <y>)`. Report it to the user: the fix needs an MSRV bump, which is a decision like a major upgrade. Don't raise `rust-version` or pass `--ignore-rust-version` unless they ask.
