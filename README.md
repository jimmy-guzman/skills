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

- [`create-pr`](skills/create-pr/SKILL.md): draft, open, or describe GitHub pull requests and GitLab merge requests that follow the repo's own conventions.
- [`fix-dep-vulns`](skills/fix-dep-vulns/SKILL.md): triage and fix dependency vulnerabilities in pnpm, uv, and pip projects, preferring lockfile refreshes and parent upgrades over overrides.
- [`review-changes`](skills/review-changes/SKILL.md): review a change with three parallel reviewers (bugs, the repo's standards, the spec), as one verified list that applies on request or leaves suggestions for the author.
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
