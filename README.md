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

They cover both sides of a change. As the author: plan it, commit it, submit it for review, then answer the feedback. As the reviewer: review it, whether it's your own work in progress or someone else's PR. Once it's done, either side can look back on it. Each skill works on its own and follows the repo's own conventions (agent docs, templates, history) before falling back to defaults.

- [`plan-changes`](skills/plan-changes/SKILL.md): turn a ticket, doc, or request into a short plan a human can approve, with the repo's facts settled and the open questions routed to their owners.
- [`commit-changes`](skills/commit-changes/SKILL.md): stage changes and write a commit message that follows the repo's own convention, falling back to Conventional Commits otherwise.
- [`submit-changes`](skills/submit-changes/SKILL.md): draft, open, or describe GitHub pull requests and GitLab merge requests that follow the repo's own conventions.
- [`review-changes`](skills/review-changes/SKILL.md): review a change with three parallel reviewers (bugs, the repo's standards, the spec), as one verified list that applies on request or leaves suggestions for the author.
- [`revise-changes`](skills/revise-changes/SKILL.md): verify the review comments already on a PR or MR against current code, fix what holds, and reply on every thread without resolving unless told to.
- [`retro-changes`](skills/retro-changes/SKILL.md): look back at a finished change, find what it cost, and turn each lesson into a code guard, a fix to your own skills, or a rule in the agent docs.

### Other

- [`fix-dep-vulns`](skills/fix-dep-vulns/SKILL.md): triage and fix dependency vulnerabilities in pnpm, uv, pip, and Cargo projects, preferring lockfile refreshes and parent upgrades over overrides.
- [`use-slack`](skills/use-slack/SKILL.md): read, search, and (after confirmation) post to Slack as the user through their browser session, no app or bot needed.
- [`talk-plainly`](skills/talk-plainly/SKILL.md): reply like a direct, busy peer, answer first, with no filler or generated-sounding patterns.

## Setup

### `use-slack`

Install just this skill, in the current project or globally:

```sh
pnpx skills add jimmy-guzman/skills --skill use-slack
pnpx skills add jimmy-guzman/skills --skill use-slack -g
```

It needs your Slack browser session in the environment, e.g. in `~/.zshrc`:

```sh
export SLACK_D_COOKIE="xoxd-..."  # DevTools > Application > Cookies > https://app.slack.com > `d`
export SLACK_URL="https://<workspace>.slack.com"
```

The script gets the `xoxc` token from the workspace page with the cookie, so there's no token to copy. The cookie is your Slack login: keep it out of repos and chats. Logging out of Slack in the browser revokes it, so copy a fresh one when the script says it expired.

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
