import frappe

# Client tools introduced by the reverted frontend-tooling feature. Their import paths no longer
# exist, so any lingering rows would break agent assembly. Idempotent: matches nothing on sites
# that never ran that migration.
CLIENT_TOOL_SLUGS = ("read_screen", "navigate", "fill", "act")


def execute():
	frappe.db.delete("Flow Agent Tool", {"tool": ["in", CLIENT_TOOL_SLUGS]})
	frappe.db.delete("Flow Tool", {"name": ["in", CLIENT_TOOL_SLUGS]})
