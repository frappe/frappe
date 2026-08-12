# Skills

Flow supports harness-neutral [Agent Skills](https://agentskills.io/) from:

```text
~/.agents/skills/<name>/SKILL.md
<cwd>/.agents/skills/<name>/SKILL.md
```

Project skills override global skills with the same name. A skill needs YAML
frontmatter followed by its instructions, and the frontmatter name must match
the directory containing `SKILL.md`:

```markdown
---
name: security-review
description: Review code changes for security issues.
---

Inspect authentication, authorization, and untrusted input boundaries.
```

At session creation, Flow adds only each skill's name, description, and path to
the system prompt. The model can load the full file with `read_file` when its
description matches a task.

Invoke a skill explicitly with:

```text
/skill:security-review check this branch
```

Flow expands the skill on the server and stores the expanded text as an ordinary
user message in the session log. Clients recognize that expanded form to render a
compact skill item, following Pi and Tau. The catalog is fixed for a session, so
start a new session after adding, removing, or changing a skill's metadata. Like Pi,
Flow reads the current `SKILL.md` contents when the skill is used, so instruction
edits can affect an existing session.

Symlinked skill directories are supported. Project and explicitly configured
skills still resolve through the server's allowed-path policy; global skills are
available through a read-only tool root.

Set `skills_enabled: false` when creating a session to disable default discovery.
Additional skill files or directories can be supplied with `skill_paths`.

Skills are instructions and may direct the model to run bundled scripts. Only use
project skills from repositories you trust.
