# Skills

Hand-written [Agent Skills](https://agentskills.io/home). Follow the [skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).

## Structure

```txt
skills/
└── {skill-name}/          # kebab-case, matches frontmatter `name`
    ├── SKILL.md
    └── references/*.md    # optional, only when SKILL.md gets long
```

`SKILL.md` frontmatter:

```markdown
---
name: { skill-name }
description: { what it does and when to use it }
---
```

## Writing

- Write for agents: what to do and why, not human getting-started guides.
- Skip what LLMs already know from training data.
- Be concise. Prefer one `SKILL.md`; fewer references is better.
- Include working examples.
