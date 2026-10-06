---
name: fix-dep-vulns
description: >
  Triage and fix security vulnerabilities in pnpm, uv, or pip dependencies
  without reaching for overrides first. Use this whenever the user shares a
  vulnerability finding, a GHSA, CVE, PYSEC, or OSV advisory, `pnpm audit`,
  `uv audit`, or `pip-audit` output, or a security alert or screenshot from
  GitLab, GitHub, Dependabot, Snyk, Renovate, or any other scanner. Also use
  it when they ask to fix, resolve, patch, bump, or clear a vulnerable
  package, even if they only name the package, and when they ask to clean up
  or remove existing overrides, constraints, or patches. Not for routine
  dependency upgrades with no advisory behind them.
compatibility: Requires pnpm, uv, or pip with pip-audit, matching the repo, plus curl and jq for registry lookups
---

# Fix dependency vulnerabilities

The goal is a healthier dependency tree, not a quiet audit.

An override clears a finding in one line, which is why it's the tempting first move. It also pins a version in place, can force a major version a parent never declared, and quietly blocks the next fix. Most findings have a better fix. Treat overrides as the last option, not the first.

## Before you start

1. Detect the ecosystem from the lockfile:
   - `pnpm-lock.yaml`: pnpm.
   - `uv.lock`: uv.
   - `requirements*.txt` or a `pyproject.toml` with no `uv.lock`: pip.
   - None of these: tell the user which ecosystems this skill covers and ask whether to adapt the same ladder to theirs.
2. Read exactly one ecosystem file: [references/pnpm.md](references/pnpm.md) or [references/python.md](references/python.md). It holds every command used below, under the headings named in italics (_Investigating_, _Fixing_, _Overrides_, _Dismissals_, _Release age_). `references/report.md` is used later in steps 3d and 6.
3. List existing overrides. pnpm: `overrides` in `pnpm-workspace.yaml`. On pnpm 11+, entries under `pnpm.overrides` or `patchedDependencies` in `package.json` are ignored (pnpm warns "The `pnpm` field in package.json is no longer read"); flag them for removal or migration to `pnpm-workspace.yaml`. uv: `override-dependencies` and `constraint-dependencies` under `[tool.uv]`. pip: `constraints.txt`. Existing overrides are a common cause of findings. An exact pin added for an old advisory holds the package below a newer fix.

## Workflow

### 1. Reproduce

Run the audit (_Investigating_). For each finding, record the package, installed versions, vulnerable range, patched range, severity, and advisory ID.

If the user's scanner reports something the local audit doesn't, the scanner probably ran against a different branch or an older lockfile. Check with `git show <branch>:<lockfile>` before changing anything. A finding that's already fixed locally just needs the change to land.

### 2. Trace

Trace every path that pulls the package in (_Investigating_). Note every parent and whether the path is production or dev-only.

Group findings that share a root. One parent upgrade or removal often clears several findings at once.

### 3. Pick a fix, in order

Work down this ladder for each finding. Stop at the first step that works.

When you surface a choice to the user, the recommended option must be the lowest-letter rung that's viable. Never recommend a lower rung — dismissal, override — while an upgrade or removal is still on the table.

**a. Refresh the lockfile.** Check the range the installed parent version declares for the package (_Investigating_). If it already allows the patched version, re-resolve just that package (_Fixing_). The lockfile was just stale. Most findings end here.

**b. Upgrade the parent.** If the refresh changes nothing, the parent probably pins an exact version or its range excludes the fix. Check what the parent's newer releases declare (_Investigating_). Same major: upgrade it. Different major: stop and ask the user. Major upgrades need a decision and usually their own ticket.

A matching peer range isn't enough on its own. Before asking the user to approve a major, read the parent's release notes for breaking config paths (`.eslintrc` → flat config), dropped output or input formats, stricter default rulesets, and deprecated flags this repo uses. Name these in the ask so "approve the major" isn't a blank cheque.

After each parent upgrade, run the smallest repo check that would catch the parent's own breakage before moving to the next finding — typecheck for API changes, lint for config-format changes, `pnpm install` for peer-dep surprises. Don't batch upgrades and run the full suite once at the end; regressions get hard to attribute.

**c. Remove the parent.** If nothing uses the parent, remove it. Umbrella packages are the usual case: they install every module a library offers. Search the code for imports (_Investigating_). If the app only uses a few scoped packages, depend on those directly and drop the umbrella. Dependencies left behind after a refactor are the other common case.

**d. Dismiss as not reachable.** A dismissal is an escape hatch like an override: it silences the signal without changing the tree. Hold it to the same bar. Only reach here when a code fix isn't available — no upstream fix exists yet, or the fix requires a major bump — **and** untrusted input can't reach the vulnerable code.

Dismiss only with evidence:

- The path is dev-only or build-time, **and** the advisory's precondition can't be met there. A build tool that parses attacker-controlled input, or a dev server reachable from a network, is still exploitable. **Or**
- The vulnerable function never receives input the app doesn't control, in production, build, and CI alike.

Read the advisory. The note has to name the precondition and why this repo can't meet it, not just "dev-only". Don't dismiss a production finding on a hunch. If you aren't sure, say so and ask.

A dismissal trades the audit signal for a quieter report. If the finding has no upstream fix, leaving it visible in audit output — with a note in the report, not a config entry — is also valid, and sometimes preferable: the recurring signal is a useful reminder to re-check when upstream patches land.

When you do dismiss (_Dismissals_):

- Every dismissal gets a note in the scanner and the comment on the config entry, using the dismissal template in [references/report.md](references/report.md).
- If the dismissal is because the fix needs a major bump, also open a ticket for the upgrade and reference it in the note. The note explains "why not now"; the ticket is how it comes back.
- Record it where the repo can see it, not only in the scanner: `pnpm-workspace.yaml`, `[tool.uv]`, or the CI invocation.
- Prefer the auto-expiring form where the ecosystem has one — uv's `ignore-until-fixed` clears itself once a patched version ships. Where there isn't one (pnpm `audit.ignore`, pip `--ignore-vuln`), write the removal condition into the comment: what has to be true for this entry to come out.
- Tell the user explicitly that you dismissed and why a code fix wasn't available.

**e. Override, as a last resort.** Only when one of these is true:

- A parent pins a vulnerable version, there's no upstream fix yet, and the vulnerable code is reachable.
- A malicious release has to be kept out of the tree today.
- A library breaks if installed more than once.
- A transitive release is broken and needs pinning back until a fix ships.

When you do add one (_Overrides_):

- Prefer the form that only narrows within ranges parents already declare: a pnpm convergence override, uv `constraint-dependencies`, a pip constraints file.
- Otherwise scope it to the parent: pnpm `parent>pkg`, a uv scoped override. pip has no scoped form; say so.
- Never cross a major the parent declared.
- Add a comment with the reason and the condition for removing it.
- Tell the user explicitly that you added an override and why the earlier steps didn't work.

Never run the auditor's auto-fix (`pnpm audit --fix`, `pip-audit --fix`). pnpm writes an override for every finding, which is the exact pattern this skill exists to avoid. pip-audit rewrites `requirements.txt` but bumps every vulnerable pin without regard to the ladder, and on pip-tools projects it edits the compiled file instead of `requirements.in`, so the next recompile reverts the fix.

### 4. Clean up existing overrides

When the repo already has overrides, constraints, or patches, check each one (_Overrides_, and _Patches_ for pnpm):

- Does the package still exist in the tree?
- Do the parents' ranges now allow the patched version?
- Does it force a major the parent never declared?

Remove the ones that fail. Removing overrides can surface findings they were hiding. That's expected, not a regression. Fix each one with the ladder above.

### 5. Verify

Don't claim a finding is fixed without evidence. Run:

1. The audit, and compare against the starting count.
2. The trace for each fixed package, to confirm only patched versions remain.
3. The repo's own type-check, lint, test, and build scripts.

If a production parent was upgraded, list what the user should smoke test by hand, such as the screens or features that library powers.

### 6. Report

Summarize using the template in [references/report.md](references/report.md): what was fixed and how, what's left and why, any dismissal notes, and any overrides added or removed.

If the user wants a merge request or pull request, hand off to the `create-pr` skill (shipped alongside this one) or whichever MR/PR skill they prefer. Otherwise draft a description with a short "What" and "Why."

## Things to watch

- **Release age.** pnpm's `minimumReleaseAge` (default one day since pnpm 11) and uv's `exclude-newer` keep fresh releases out of the tree. A fix published inside that window won't install yet. Tell the user instead of working around it (_Release age_). The delay protects against malicious releases.
- **Registry mirrors.** Company mirrors can lag the public registry. If the registry lookup doesn't show a version the advisory mentions, say so. It's an infrastructure question, not a tree problem.
- **Targeted updates.** Re-resolve one package (`pnpm update <pkg>`, `uv lock --upgrade-package <pkg>`) rather than everything. A bare update bumps every package within range and turns a security fix into a large, hard-to-review diff.
- **Prod vs dev.** `pnpm why` labels dev paths. `uv audit --no-dev` drops the `dev` group, but other groups and extras still count; check `uv tree --invert` for the real path. pip repos usually split `requirements.txt` from `requirements-dev.txt`; a finding only in the dev file is dev-only.
- **Peer warnings.** After removing an umbrella package, pnpm may warn about missing peers the umbrella used to satisfy. Add them as direct dependencies.
