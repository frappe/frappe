import frappe

# Standard workspaces whose icon names were renamed in the JSON fixtures when
# Frappe migrated to the lucide-static icon set, but for which no accompanying
# data patch shipped. Existing sites still hold the old names in
# `tabWorkspace.icon`; those IDs don't exist in the lucide sprite, so the
# `<use href="#icon-...">` renders blank in the workspace sidebar/dock.
#
# The rewrite is guarded on the OLD value: a user who has explicitly picked a
# different icon via the workspace customization UI keeps their choice. Rows
# already holding the new lucide name are left untouched, so this patch is
# idempotent.
RENAMES = [
	("Website", "website", "app-window"),
	("Integrations", "integration", "cable"),
	("Welcome Workspace", "image-view", "sparkles"),
]


def execute():
	Workspace = frappe.qb.DocType("Workspace")

	for name, old_icon, new_icon in RENAMES:
		frappe.qb.update(Workspace).set(Workspace.icon, new_icon).where(
			(Workspace.name == name) & (Workspace.icon == old_icon)
		).run()
