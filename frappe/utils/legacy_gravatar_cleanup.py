"""One-time cleanup flow for legacy Gravatar URLs stored before Gravatar support was removed.
Can be dropped when skip_gravatar_deletion_prompt is 1 for the majority of sites, or in the
next major release.
"""

import frappe
from frappe.utils import cint
from frappe.utils.background_jobs import is_job_enqueued

GRAVATAR_URL_PATTERN = "%gravatar.com%"
GRAVATAR_DELETION_JOB_ID = "delete_legacy_gravatar_image_urls"
SKIP_GRAVATAR_DELETION_PROMPT = "skip_gravatar_deletion_prompt"
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

	if cint(frappe.defaults.get_global_default(SKIP_GRAVATAR_DELETION_PROMPT)):
		return False

	if is_job_enqueued(GRAVATAR_DELETION_JOB_ID):
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
		frappe.defaults.set_global_default(SKIP_GRAVATAR_DELETION_PROMPT, 1)

	queued = False
	if cint(delete_gravatar_urls):
		frappe.enqueue(
			delete_gravatar_image_urls,
			queue="long",
			now=frappe.in_test,
			enqueue_after_commit=not frappe.in_test,
			job_id=GRAVATAR_DELETION_JOB_ID,
			deduplicate=True,
		)
		queued = True

	return {"queued": queued}


def delete_gravatar_image_urls():
	for doctype, fieldname in get_gravatar_image_fields():
		filters = {fieldname: ("like", GRAVATAR_URL_PATTERN)}
		frappe.db.set_value(doctype, filters, fieldname, "", update_modified=False)

	frappe.defaults.set_global_default(SKIP_GRAVATAR_DELETION_PROMPT, 1)
