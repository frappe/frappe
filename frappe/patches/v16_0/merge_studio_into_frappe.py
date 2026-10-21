"""Sites that installed Studio as its own app get it from frappe now; the tables stay."""

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
