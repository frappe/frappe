import click

import frappe

# Where a workspace goes when nothing says where it belongs. Both are custom modules the site
# owns rather than modules any app ships. See `ensure_module`.
PRIVATE_MODULE = "Private"
CUSTOM_MODULE = "Custom Workspaces"


def execute():
	"""Give every workspace without a module one, so `Workspace.module` can become mandatory.

	No guessing: a user's own page goes to `Private`, everything else to `Custom Workspaces`, a
	triage list a workspace manager sorts out later.
	"""
	workspaces = frappe.get_all(
		"Workspace",
		filters={"module": ["in", ["", None]]},
		fields=["name", "for_user"],
	)
	if not workspaces:
		return

	buckets = {
		PRIVATE_MODULE: [w.name for w in workspaces if w.for_user],
		CUSTOM_MODULE: [w.name for w in workspaces if not w.for_user],
	}

	for module, names in buckets.items():
		# only create a module when something is going into it
		if not names:
			continue

		ensure_module(module)
		frappe.db.set_value("Workspace", {"name": ["in", names]}, "module", module, update_modified=False)
		click.secho(f"  {len(names)} workspace(s) -> {module}", fg="green")


def ensure_module(module: str) -> None:
	"""Create the destination module if the site doesn't have it yet.

	`custom` so no app owns it: an app's uninstall must not take the site's workspaces with it.
	"""
	if frappe.db.exists("Module Def", module):
		return

	frappe.get_doc({"doctype": "Module Def", "module_name": module, "custom": 1}).insert(
		ignore_permissions=True
	)
