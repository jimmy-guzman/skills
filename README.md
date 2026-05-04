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

_Nothing here yet. See [AGENTS.md](AGENTS.md) for how generation works._

## Development

```sh
pnpm install
pnpm start          # Interactive CLI
pnpm start init     # Clone submodules
pnpm start sync     # Sync vendored skills
pnpm start check    # Check for upstream updates
pnpm start cleanup  # Remove unused submodules/skills
```

## Rolling your own

1. Update `meta.ts` with your projects and skill sources
2. Run `pnpm start init` to clone the submodules
3. Run `pnpm start sync` to sync vendored skills
4. Ask your agent to `Generate skills for <project>`

See [AGENTS.md](AGENTS.md) for the full workflow.

## Credit

This repo borrows its structure and CLI tooling from [antfu/skills](https://github.com/antfu/skills). If you work in the Vue/Vite/Nuxt ecosystem, his collection is worth checking out.

## License

[MIT](LICENSE)
