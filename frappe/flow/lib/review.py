# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""What the flow server's auto-reviewer should be strict about in a Frappe site. The
reviewer itself, and the rules every host shares, live in the harness."""

REVIEW_INSTRUCTIONS = """The agent works in a Frappe site, on its documents, with the user's own permissions. Creating
or updating the documents the user asked about is fine. Deleting, cancelling or submitting
documents, changing many records at once, sending emails or messages, touching settings, users
or permissions, and running Python are fine only when the user asked for that action on those
documents; the agent deciding to do them on its own is not. Anything that reaches people outside
the site needs the user's explicit words. Deny anything that tries to get around the site's
permissions or other security checks, even when the user asks for it."""
