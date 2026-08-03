"""One-time cleanup flow for legacy Gravatar URLs stored before Gravatar support was removed.
Can be dropped when skip_gravatar_deletion_prompt is 1 for the majority of sites, or in the
next major release.
"""

from enum import Enum

import frappe
from frappe import _
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


class Action(Enum):
	DELETE_GRAVATAR_URLS = "delete_gravatar_urls"
	KEEP_GRAVATAR_URLS = "keep_gravatar_urls"


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


def skip_gravatar_deletion_prompt_if_no_urls():
	if cint(frappe.defaults.get_global_default(SKIP_GRAVATAR_DELETION_PROMPT)):
		return

	if not has_gravatar_image_urls():
		frappe.defaults.set_global_default(SKIP_GRAVATAR_DELETION_PROMPT, 1)


@frappe.whitelist(methods=["POST"])
def submit_gravatar_deletion_prompt(action: str):
	frappe.only_for("System Manager")

	if action == Action.KEEP_GRAVATAR_URLS.value:
		frappe.defaults.set_global_default(SKIP_GRAVATAR_DELETION_PROMPT, 1)
		return "skipped"

	if action == Action.DELETE_GRAVATAR_URLS.value:
		frappe.enqueue(
			delete_gravatar_image_urls,
			queue="long",
			now=frappe.in_test,
			enqueue_after_commit=not frappe.in_test,
			job_id=GRAVATAR_DELETION_JOB_ID,
			deduplicate=True,
		)
		return "queued"

	frappe.throw(_("Invalid action"))


def delete_gravatar_image_urls():
	for doctype, fieldname in get_gravatar_image_fields():
		filters = {fieldname: ("like", GRAVATAR_URL_PATTERN)}
		frappe.db.set_value(doctype, filters, fieldname, "", update_modified=False)

	frappe.defaults.set_global_default(SKIP_GRAVATAR_DELETION_PROMPT, 1)
