# Jimmy Guzman's Skills

## Installation

```sh
pnpx skills add jimmy-guzman/skills
```

Or globally:

```sh
pnpx skills add jimmy-guzman/skills -g
```

## Skills

### Changes

They cover both sides of a change. As the author: plan it, commit it, submit it for review, then answer the feedback. As the reviewer: review it, whether it's your own work in progress or someone else's PR. Each skill works on its own and follows the repo's own conventions (agent docs, templates, history) before falling back to defaults.

- [`plan-changes`](skills/plan-changes/SKILL.md): turn a ticket, doc, or request into a short plan a human can approve, with the repo's facts settled and the open questions routed to their owners.
- [`commit-changes`](skills/commit-changes/SKILL.md): stage changes and write a commit message that follows the repo's own convention, falling back to Conventional Commits otherwise.
- [`submit-changes`](skills/submit-changes/SKILL.md): draft, open, or describe GitHub pull requests and GitLab merge requests that follow the repo's own conventions.
- [`review-changes`](skills/review-changes/SKILL.md): review a change with three parallel reviewers (bugs, the repo's standards, the spec), as one verified list that applies on request or leaves suggestions for the author.
- [`revise-changes`](skills/revise-changes/SKILL.md): verify the review comments already on a PR or MR against current code, fix what holds, and reply on every thread without resolving unless told to.

### Other

- [`fix-dep-vulns`](skills/fix-dep-vulns/SKILL.md): triage and fix dependency vulnerabilities in pnpm, uv, and pip projects, preferring lockfile refreshes and parent upgrades over overrides.
- [`talk-plainly`](skills/talk-plainly/SKILL.md): reply like a direct, busy peer, answer first, with no filler or generated-sounding patterns.

## Adding a skill

Create `skills/<name>/SKILL.md`. See [AGENTS.md](AGENTS.md) for conventions.

## Development

Install [mise](https://mise.jdx.dev), then run every check with one command:

```sh
mise install
mise run check
```

`check` runs the skill validator, ruff, and every skill's unit tests.

Skills themselves need only `python3`. mise, uv, and ruff are for repo development.

## License

[MIT](LICENSE)
