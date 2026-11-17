"""Software Bill of Materials (SBOM) of a site, in SPDX 2.3 JSON format."""

import json

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.utils import now_datetime
from frappe.utils.sbom.collector import collect
from frappe.utils.sbom.spdx import to_spdx

ATTACH_TO = "Installed Applications"


@frappe.whitelist(methods=["POST"])
def generate_sbom():
	frappe.only_for("System Manager")

	job = frappe.enqueue(build_and_attach_sbom, queue="long", job_id="generate_sbom", deduplicate=True)
	if job is None:
		frappe.msgprint(
			_("SBOM generation is already in progress. You will get a notification when it is ready.")
		)
	else:
		frappe.msgprint(_("SBOM generation started. You will get a notification when it is ready."))


def build_and_attach_sbom():
	try:
		document = to_spdx(collect(frappe.get_installed_apps(_ensure_on_bench=True)), frappe.local.site)
		frappe.get_doc(
			{
				"doctype": "File",
				"attached_to_doctype": ATTACH_TO,
				"attached_to_name": ATTACH_TO,
				"file_name": f"sbom-{frappe.local.site}-{now_datetime():%Y%m%d-%H%M%S}.spdx.json",
				"is_private": 1,
				"content": json.dumps(document, indent=2),
			}
		).insert()
	except Exception:
		# The job commits on success only, so commit the error log and the alert here.
		frappe.db.rollback()
		frappe.log_error(title=_("SBOM generation failed"))
		_notify(_("SBOM generation failed"))
		frappe.db.commit()
		return

	_notify(_("SBOM is ready"))


def _notify(subject: str):
	make_notification_logs(
		{
			"type": "Alert",
			"document_type": ATTACH_TO,
			"document_name": ATTACH_TO,
			"subject": subject,
		},
		[frappe.db.get_value("User", frappe.session.user, "email")],
	)
