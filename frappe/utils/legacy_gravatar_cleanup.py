"""One-time cleanup flow for legacy Gravatar URLs stored before Gravatar support was removed.
Can be dropped when skip_gravatar_deletion_prompt is 1 for the majority of sites, or in the
next major release.
"""

import frappe
from frappe.utils import cint

GRAVATAR_URL_PATTERN = "%gravatar.com%"
BASE_GRAVATAR_IMAGE_FIELDS = (
	("User", "user_image"),
	("Contact", "image"),
)
ERPNEXT_GRAVATAR_IMAGE_FIELDS = (("Lead", "image"),)


def get_gravatar_image_fields():
	fields = list(BASE_GRAVATAR_IMAGE_FIELDS)
	if "erpnext" in frappe.get_installed_apps():
		fields.extend(ERPNEXT_GRAVATAR_IMAGE_FIELDS)
	return fields


def should_show_gravatar_deletion_prompt():
	if "System Manager" not in frappe.get_roles():
		return False

	if cint(frappe.get_single_value("System Settings", "skip_gravatar_deletion_prompt")):
		return False

	return has_gravatar_image_urls()


def has_gravatar_image_urls():
	return any(
		frappe.db.exists(doctype, {fieldname: ("like", GRAVATAR_URL_PATTERN)})
		for doctype, fieldname in get_gravatar_image_fields()
	)


@frappe.whitelist(methods=["POST"])
def submit_gravatar_deletion_prompt(delete_gravatar_urls: bool = False, skip_prompt: bool = False):
	frappe.only_for("System Manager")

	if cint(skip_prompt):
		frappe.db.set_single_value("System Settings", "skip_gravatar_deletion_prompt", 1)

	queued = False
	if cint(delete_gravatar_urls):
		frappe.enqueue(
			delete_gravatar_image_urls,
			queue="long",
			now=frappe.in_test,
			enqueue_after_commit=not frappe.in_test,
			job_id="delete_legacy_gravatar_image_urls",
			deduplicate=True,
		)
		queued = True

	return {"queued": queued}


def delete_gravatar_image_urls():
	for doctype, fieldname in get_gravatar_image_fields():
		filters = {fieldname: ("like", GRAVATAR_URL_PATTERN)}
		frappe.db.set_value(doctype, filters, fieldname, "", update_modified=False)

	frappe.db.set_single_value("System Settings", "skip_gravatar_deletion_prompt", 1)
