---
title: Authoring Guide
order: 10
roles:
  - System Manager
---

# Authoring Guide

## Frontmatter

Only three frontmatter keys are supported:

| Key | Purpose |
| --- | --- |
| `title` | Page title shown in navigation |
| `order` | Sort order among siblings |
| `roles` | Roles allowed to view the page |

## Role defaults

If `roles` is omitted, the page is visible to **Desk User**. Multiple roles use
any-match semantics: a user needs only one listed role.

## Language trees

Put documentation under a language directory inside `docs/`:

```text
{app_package}/docs/
  en/guides/setup.md
  de/guides/setup.md
```

The first directory must be a Frappe **Language** code. It is stripped from the
logical path. Routes include the locale: `/desk/docs/de/guides/setup`.

When you open a language-neutral route, Frappe redirects to your language only
when a localized variant exists. Otherwise it uses English. Use the language
selector in the sidebar to switch between available variants for the current
page.

For an explicit locale in the URL, Frappe tries the exact language, then the
parent language (`de-CH` → `de`), then English.

When an English page exists, a localized file replaces its `title`, body, and
relative assets. It inherits `order` and `roles` from the English page.

Localized-only pages have no English equivalent. They appear in navigation only
for the exact or parent language and use their own `title`, `order`, `roles`,
body, and assets. A shared link still opens the page for users in other
languages.

## Multi-app composition

Later installed apps replace the page body and metadata at an identical logical
path. Child paths continue to merge independently.

For translations, a localized variant applies only when it comes from the app
that owns the English page or a later installed app.

## Example page

```md
---
title: Getting Started
order: 1
roles:
  - Desk User
  - System Manager
---

# Getting Started

Your documentation content here.
```
