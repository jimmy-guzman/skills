# Jimmy Guzman's Skills

[Agent Skills](https://agentskills.io/home) for the tools and frameworks I use. Opinionated where it matters.

## Installation

```sh
pnpx skills add jimmy-guzman/skills --skill='*'
```

Or globally:

```sh
pnpx skills add jimmy-guzman/skills --skill='*' -g
```

## Skills

- [`create-pr`](skills/create-pr/SKILL.md): draft, open, or describe GitHub pull requests and GitLab merge requests that follow the repo's own conventions.
- [`fix-dep-vulns`](skills/fix-dep-vulns/SKILL.md): triage and fix dependency vulnerabilities in pnpm, uv, and pip projects, preferring lockfile refreshes and parent upgrades over overrides.
- [`talk-plainly`](skills/talk-plainly/SKILL.md): reply like a direct, busy peer, answer first, with no filler or generated-sounding patterns.

## Adding a skill

Create `skills/<name>/SKILL.md`. See [AGENTS.md](AGENTS.md) for conventions.

## Credit

Inspired by [antfu/skills](https://github.com/antfu/skills) and [mattpocock/skills](https://github.com/mattpocock/skills).

## License

[MIT](LICENSE)
