---
title: In-app documentation
order: 0
roles:
  - System Manager
---

# In-app documentation

Apps can ship user documentation as Markdown files under a `docs/` folder in the app package.

## Authoring convention

- Put files in `{app_package}/docs/{language}/`
- Folders and file names define the navigation tree
- Use `index.md` for a directory landing page
- Optional frontmatter keys: `title`, `order`, `roles`
- Omit `roles` to allow all **Desk User** accounts
- Later installed apps override pages at the same logical path

See [Getting Started](getting-started) for a walkthrough.
