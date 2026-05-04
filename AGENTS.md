# Skills Generator

Generate [Agent Skills](https://agentskills.io/home) from project documentation.

PLEASE STRICTLY FOLLOW THE BEST PRACTICES FOR SKILL: <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>

- Focus on what agents can do with the tool, not how humans install or get started with it.
- Skip content that LLMs already know from training data.
- Keep skills concise. Fewer references is better.

## Skill Source Types

There are two types of skill sources. The project lists are defined in `meta.ts`:

### Type 1: Generated Skills (`sources/`)

For OSS projects that don't have existing skills. We clone the repo as a submodule and generate skills from their documentation.

- Workflow: Read docs -> Understand -> Generate skills
- Source: `sources/{project}/docs/`

### Type 2: Synced Skills (`vendor/`)

For projects that already maintain their own skills. We clone their repo as a submodule and copy specified skills to ours.

- Workflow: Pull updates -> Copy specified skills (with optional renaming)
- Source: `vendor/{project}/skills/{skill-name}/`
- Config: Each vendor specifies which skills to sync and their output names in `meta.ts`

### Type 3: Hand-written Skills

For skills written with personal preferences, experience, tastes and best practices.

You don't need to do anything about them unless being asked.

## Repository Structure

```txt
.
├── meta.ts                     # Project metadata (repos & URLs)
├── instructions/               # Instructions for generating skills
│   └── {project}.md            # Instructions for generating skills for {project}
│
├── sources/                    # Type 1: OSS repos (generate from docs)
│   └── {project}/
│       └── docs/               # Read documentation from here
│
├── vendor/                     # Type 2: Projects with existing skills (sync only)
│   └── {project}/
│       └── skills/
│           └── {skill-name}/   # Individual skills to sync
│
└── skills/                     # Output directory (generated or synced)
    └── {output-name}/
        ├── SKILL.md           # Index of all skills
        ├── GENERATION.md       # Tracking metadata (for generated skills)
        ├── SYNC.md             # Tracking metadata (for synced skills)
        └── references/
            └── *.md            # Individual skill files
```

For Type 1 (generated), the `skills/{project}/` name must match `sources/{project}/`. For Type 2 (synced), the output name is configured in `meta.ts` and may differ from the source skill name.

## Workflows

### For Generated Skills (Type 1)

#### Adding a New Project

1. Add entry to `meta.ts` in the `submodules` object:

   ```ts
   export const submodules: Record<string, string> = {
     // ... existing entries
     "new-project": "https://github.com/org/repo",
   };
   ```

2. Run sync script to clone the submodule:

   ```bash
   pnpm start init -y
   ```

   This clones the repository to `sources/{project}/`

3. Follow the generation guide below to create the skills

#### General Instructions for Generation

- Focus on what agents can do, not user-facing guides or introductions. Skip common knowledge.
- Categorize references into `core`, `features`, `best-practices`, `advanced`, etc. Prefix the reference file name with the category. Create more categories if needed.

#### Creating New Skills

- Read source docs from `sources/{project}/docs/`
- Read the instructions in `instructions/{project}.md` if one exists
- Understand the documentation thoroughly
- Create skill files in `skills/{project}/references/`
- Create `SKILL.md` index listing all skills
- Create `GENERATION.md` with the source git SHA

#### Updating Generated Skills

1. Check git diff since the SHA recorded in `GENERATION.md`:

   ```bash
   cd sources/{project}
   git diff {old-sha}..HEAD -- docs/
   ```

2. Update affected skill files based on changes
3. Update `SKILL.md` with the new version of the tool/project and skills table.
4. Update `GENERATION.md` with new SHA

### For Synced Skills (Type 2)

#### Initial Sync

1. Copy specified skills from `vendor/{project}/skills/{skill-name}/` to `skills/{output-name}/`
2. Create `SYNC.md` with the vendor git SHA

#### Updating Synced Skills

1. Check git diff since the SHA recorded in `SYNC.md`:

   ```bash
   cd vendor/{project}
   git diff {old-sha}..HEAD -- skills/{skill-name}/
   ```

2. Copy changed files from `vendor/{project}/skills/{skill-name}/` to `skills/{output-name}/`
3. Update `SYNC.md` with new SHA

Do NOT modify synced skills manually. Changes should go upstream to the vendor project.

## File Formats

### `SKILL.md`

Index file listing all skills with brief descriptions. Name should be in `kebab-case`.

The version should be the date of the last sync.

Also record the version of the tool/project when the skills were generated.

```markdown
---
name: { name }
description: { description }
metadata:
  author: Jimmy Guzman
  version: "2026.1.1"
  source: Generated from {source-url}, scripts located at https://github.com/jimmy-guzman/skills
---

> The skill is based on {project} v{version}, generated at {date}.

// Some concise summary/context/introduction of the project

## Core References

| Topic           | Description                                       | Reference                                        |
| --------------- | ------------------------------------------------- | ------------------------------------------------ |
| Markdown Syntax | Slide separators, frontmatter, notes, code blocks | [core-syntax](references/core-syntax.md)         |
| Animations      | v-click, v-clicks, motion, transitions            | [core-animations](references/core-animations.md) |

## Features

### Feature a

| Topic            | Description              | Reference                                |
| ---------------- | ------------------------ | ---------------------------------------- |
| Feature A Editor | Description of feature a | [feature-a](references/feature-a-foo.md) |

// ...
```

### `GENERATION.md`

Tracking metadata for generated skills (Type 1):

```markdown
# Generation Info

- **Source:** `sources/{project}`
- **Git SHA:** `abc123def456...`
- **Generated:** 2024-01-15
```

### `SYNC.md`

Tracking metadata for synced skills (Type 2):

```markdown
# Sync Info

- **Source:** `vendor/{project}/skills/{skill-name}`
- **Git SHA:** `abc123def456...`
- **Synced:** 2024-01-15
```

### `references/*.md`

Individual skill files. One concept per file.

Include source documentation links at the end of the file.

```markdown
---
name: { name }
description: { description }
---

# {Concept Name}

Brief description of what this skill covers.

## Usage

Code examples and practical patterns.

## Key Points

- Important detail 1
- Important detail 2

<!--
Source references:
- {source-url}
- {source-url}
-->
```

## Writing Guidelines

When generating skills (Type 1 only):

1. Rewrite for agents. Don't copy docs verbatim; synthesize for LLM consumption.
2. Be practical. Focus on usage patterns and code examples.
3. Be concise. Remove fluff, keep what matters.
4. One concept per file. Split large topics into separate skill files.
5. Include code. Always provide working code examples.
6. Explain why, not just how.

## Supported Projects

See `meta.ts` for the canonical list of projects and their repository URLs.
