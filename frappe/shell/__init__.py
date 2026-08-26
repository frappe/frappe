# The desk v2 shell: the framework hosts one SPA and owns the URL space beneath /apps.
#
# The framework claims a single top-level segment, SHELL_ROOT, and every app lives
# under it at a prefix of its own: /apps/desk, /apps/crm. An app declares that prefix
# with the `app_prefix` hook, or declares nothing and gets its own name.
#
# Nothing here touches desk v1. `/desk`, `/app` and every `www/` page resolve exactly
# as they did; the shell is reached only through the segment below.

# The one top-level segment the framework claims. Everything the shell serves is
# beneath it, which is what makes the collision surface app-vs-app instead of
# app-vs-the-entire-website (#42062 charter item 6, amended 2026-08-26).
SHELL_ROOT = "apps"
