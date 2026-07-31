---
title: Authoring Guide
order: 10
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

## Multi-app composition

Later installed apps replace the page body and metadata at an identical logical
path. Child paths continue to merge independently.

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
