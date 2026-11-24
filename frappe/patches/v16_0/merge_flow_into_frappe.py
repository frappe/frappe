"""Sites that installed Flow as its own app get it from frappe now; the tables stay."""

import click

import frappe
from frappe.installer import remove_from_installed_apps


def execute():
	if "flow" not in frappe.get_installed_apps():
		return

	if frappe.db.exists("Module Def", "Flow"):
		frappe.db.set_value("Module Def", "Flow", "app_name", "frappe", update_modified=False)

	remove_from_installed_apps("flow")
	# hooks stay site-cached past the removal; the rest of this migrate must not see flow's
	frappe.clear_cache()
	# the module map was built at connect with the app owning the Flow module; without a
	# rebuild the model sync looks for frappe's Flow DocTypes inside the app and fails
	frappe.setup_module_map(include_all_apps=False)
	click.secho(
		"Flow is part of frappe now. Run `bench remove-app flow` once every site on this bench has migrated.",
		fg="yellow",
	)
