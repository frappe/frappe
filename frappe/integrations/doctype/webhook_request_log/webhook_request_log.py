# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.integrations.doctype.webhook.webhook import enqueue_webhook_retry
from frappe.model.document import Document


class WebhookRequestLog(Document):
	_DOCTYPE_NAME = "Webhook Request Log"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		attempt: DF.Int
		data: DF.Code | None
		error: DF.Text | None
		headers: DF.Code | None
		next_retry: DF.Datetime | None
		reference_doctype: DF.Data | None
		reference_document: DF.Data | None
		response: DF.Code | None
		status: DF.Literal["", "Delivered", "Failed", "Exhausted"]
		url: DF.Text | None
		user: DF.Link | None
		webhook: DF.Link | None
	# end: auto-generated types

	@frappe.whitelist(methods=["POST"])
	def retry(self):
		# run_doc_method can build self from a copy the client sent; check the stored log
		self.reload()
		if self.status not in ("Failed", "Exhausted"):
			frappe.throw(_("Only failed or exhausted requests can be retried"), title=_("Cannot Retry"))

		webhook = frappe.get_lazy_doc("Webhook", self.webhook)
		webhook.check_permission("write")
		if not webhook.enabled:
			frappe.throw(
				_("Enable Webhook {0} to retry this request").format(self.webhook), title=_("Cannot Retry")
			)

		if not enqueue_webhook_retry(self.name, webhook.background_jobs_queue or "default"):
			frappe.throw(_("A retry for this request is already queued"), title=_("Cannot Retry"))

	@staticmethod
	def clear_old_logs(days=30):
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("Webhook Request Log")
		frappe.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))
