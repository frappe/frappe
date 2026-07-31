---
title: Getting Started
order: 1
roles:
  - System Manager
---

# Getting started

Open **Documentation** from the Desk sidebar or navigate to `/desk/docs/en`.

Each page is discovered at runtime from installed apps. Restrict a page to specific roles with frontmatter:

```yaml
---
title: Sales Guide
roles:
  - Sales User
---
```

Users need any one of the listed roles to see the page in the tree and open it directly.
