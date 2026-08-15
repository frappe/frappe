# Skills

Skills are reusable task instructions stored in `SKILL.md` files. Flow discovers them when a session is created.

## Locations and precedence

Flow looks in these locations:

```text
~/.agents/skills/<name>/SKILL.md
<cwd>/.agents/skills/<name>/SKILL.md
```

Project skills override global skills with the same name. `SessionConfig.skill_paths` can add files or directories; relative paths are resolved from `cwd`. Set `skills_enabled: false` to disable the default locations.

## File format

The directory name and frontmatter name must match. The frontmatter needs a description.

```markdown
---
name: security-review
description: Review code changes for security problems.
---

Inspect authentication, authorization, and untrusted-input boundaries.
```

Names use lowercase letters, digits, and single hyphens.

## How Flow uses a skill

At session creation, Flow records the selected skill catalog and adds model-invocable skill names, descriptions, and locations to the system prompt. The model can use `read_file` to load an applicable skill.

Users can invoke one directly:

```text
/skill:security-review review the current changes
```

Flow reads and expands the skill on the server, then saves that expanded text as the user message. The catalog remains fixed for the session, but edits to the instruction body affect later explicit invocations. Start a new session after changing skill names or descriptions.

Skill files may contain scripts or instructions that lead to code execution. Treat skills, especially project-provided ones, as trusted content.
