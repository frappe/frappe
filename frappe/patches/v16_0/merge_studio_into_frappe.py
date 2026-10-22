"""Sites that installed Studio as its own app get it from frappe now; the tables stay."""

import click

import frappe
from frappe.installer import remove_from_installed_apps
from frappe.query_builder.functions import Replace


def execute():
	if "studio" not in frappe.get_installed_apps():
		return

	patch_log = frappe.qb.DocType("Patch Log")
	(
		frappe.qb.update(patch_log)
		.set(
			patch_log.patch,
			Replace(patch_log.patch, "studio.studio.doctype.", "frappe.studio.doctype."),
		)
		.where(patch_log.patch.like("studio.studio.doctype.%"))
	).run()

	if frappe.db.exists("Module Def", "Studio"):
		frappe.db.set_value("Module Def", "Studio", "app_name", "frappe", update_modified=False)

	remove_from_installed_apps("studio")
	# hooks stay site-cached past the removal; the rest of this migrate must not see studio's
	frappe.clear_cache()
	# the module map was built at connect, before the removal; without a rebuild the model sync
	# never walks frappe's Studio module and the DocTypes keep the standalone definitions
	frappe.setup_module_map(include_all_apps=False)
	click.secho(
		"Studio is part of frappe now. Run `bench remove-app studio` once every site on this bench has migrated.",
		fg="yellow",
	)
