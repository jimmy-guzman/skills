# Python reference

Covers uv (a `uv.lock`) and pip (`requirements*.txt`, optionally compiled from `requirements.in` by pip-tools). Headings match the italic names in `SKILL.md`; each has a uv block and a pip block where they differ.

`uv audit` needs uv 0.11 or newer. Check `uv --version`, and `required-version` under `[tool.uv]` if set.

## Contents

- Investigating
- Fixing
- Overrides
- Dismissals
- Release age

## Investigating

uv:

```sh
uv audit                                  # all findings, from uv.lock
uv audit --no-dev                         # excludes the dev group only; other groups and extras still count
uv audit --locked                         # fail if the lockfile is stale
uv tree --invert --package <pkg>          # every path that pulls <pkg> in
uv tree --outdated                        # newer versions available for each locked package
```

pip:

```sh
uvx pip-audit -r requirements.txt         # findings; resolves deps like pip install would. Or: pipx run pip-audit
uvx pip-audit -r requirements.txt --no-deps   # fully pinned files only, much faster
uvx pipdeptree -r -p <pkg>                # every path that pulls <pkg> in (needs the env installed). Or: pipx run pipdeptree
pip index versions <pkg>                  # published versions
```

`uvx` needs uv. If the repo has no uv, use `pipx run` or install the tool into the environment.

Strip `-e` and local-path lines before passing a file to pip-audit; it can't resolve them. Audit each requirements file the repo installs. A finding only in `requirements-dev.txt` is dev-only.

Both, for what a specific release declares (there is no `uv view`):

```sh
curl -s https://pypi.org/pypi/<pkg>/<version>/json | jq -r '.info.requires_dist[]'
curl -s https://pypi.org/pypi/<pkg>/json | jq -r '.info.version'           # latest
```

Empty `requires_dist` output for the dependency means that release no longer depends on it at all.

Checking what the code imports, before removing a parent:

```sh
grep -rnE "^\s*(from|import)\s+<module>" --include='*.py' .
```

The import name can differ from the distribution name (`PIL` for `pillow`, `yaml` for `PyYAML`). Check the package's top-level module before concluding nothing uses it.

## Fixing

uv:

```sh
uv lock --upgrade-package <pkg>           # re-resolve <pkg> within existing ranges
uv lock --upgrade-package <pkg>==<ver>    # to a specific version, if ranges allow it
uv add "<parent>>=<version>"              # upgrade a direct dependency
uv remove <parent>                        # remove a direct dependency
uv sync                                   # apply the lockfile to the environment
```

If `uv lock --upgrade-package` leaves the lockfile unchanged, a parent's range excludes the fix. Move to upgrading the parent.

pip:

- Pinned `requirements.txt`: edit the pin, then `pip install -r requirements.txt` to confirm it resolves.
- pip-tools (`requirements.in` present): `uvx pip-compile --upgrade-package <pkg> requirements.in`, never edit the compiled file by hand.
- Upgrade or remove a parent in the `.in` file or `pyproject.toml`, then recompile.

## Overrides

uv has two settings under `[tool.uv]` in `pyproject.toml`. TOML allows comments, so every entry should carry one.

`constraint-dependencies` only narrows. It applies to packages already in the tree and can't force a version a parent's range excludes. Use it for a security floor when parents already allow the fix. This is the equivalent of a pnpm convergence override.

```toml
[tool.uv]
constraint-dependencies = [
  # Reason: <advisory>. Remove when: every parent requires <pkg> >= <fixed>.
  "<pkg>>=<fixed>",
]
```

`override-dependencies` replaces what parents declare and can force past their ranges. Scope it to the parent release that needs it:

```toml
[tool.uv]
override-dependencies = [
  # Reason: <advisory>, <parent> <version> pins <pkg> exact.
  # Remove when: <parent> ships a release with <pkg> >= <fixed>.
  { package = { name = "<parent>", version = "<version>" }, dependencies = ["<pkg>>=<fixed>"] },
]
```

A bare string (`"<pkg>>=<fixed>"`) applies to every parent. Avoid it unless the scoped form can't express the fix.

pip: a constraints file, installed with `pip install -r requirements.txt -c constraints.txt` (or `pip-compile -c constraints.txt`). It only narrows and can't be scoped to a parent. Comment each line.

## Dismissals

uv: `uv audit` reads a persisted ignore list. Prefer `ignore-until-fixed`, which stops ignoring once a fixed version is available.

```toml
[tool.uv.audit]
ignore-until-fixed = [
  # Dev-only, <pkg> via <parent>. Remove when <parent> ships <major>.
  "GHSA-xxxx-xxxx-xxxx",
]
```

pip: `pip-audit --ignore-vuln <id>` has no config-file form. Put it on the audit command in CI with a comment, and record the same note in the scanner's dismissal.

## Release age

uv's `exclude-newer` (under `[tool.uv]`, or `UV_EXCLUDE_NEWER`) rejects releases newer than a date or younger than a duration such as `"1 week"`. `exclude-newer-package` does the same per package. If the patched release is inside that window, `uv lock --upgrade-package` won't pick it up. Report it to the user. Don't lower the setting unless they ask.

pip has no equivalent.
