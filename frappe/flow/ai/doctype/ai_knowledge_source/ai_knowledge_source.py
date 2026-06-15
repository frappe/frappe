# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document

REQUIRED_INPUT = {
	"Text": "content",
	"File": "file",
	"URL": "url",
	"DocType": "reference_doctype",
}


class AIKnowledgeSource(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		chunk_count: DF.Int
		content: DF.LongText | None
		content_fields: DF.SmallText | None
		error_log: DF.LongText | None
		file: DF.Attach | None
		filters: DF.JSON | None
		knowledge_base: DF.Link
		last_synced_at: DF.Datetime | None
		reference_doctype: DF.Link | None
		source_type: DF.Literal["Text", "File", "URL", "DocType"]
		status: DF.Literal["Pending", "Processing", "Completed", "Failed"]
		title: DF.Data
		url: DF.Data | None
	# end: auto-generated types

	def validate(self):
		fieldname = REQUIRED_INPUT.get(self.source_type)
		if fieldname and not self.get(fieldname):
			frappe.throw(
				_("{0} is required for a {1} source.").format(
					_(self.meta.get_label(fieldname)), _(self.source_type)
				),
				frappe.MandatoryError,
			)
		if self.source_type == "DocType" and not (self.content_fields or "").strip():
			frappe.throw(
				_("Content Fields is required for a DocType source."),
				frappe.MandatoryError,
			)

	def after_insert(self):
		from flow.knowledge.ingest import enqueue_ingestion

		enqueue_ingestion(self.name)

	def on_trash(self):
		from flow.knowledge.ingest import purge_source

		purge_source(self.name)

	@frappe.whitelist()
	def resync(self):
		from flow.knowledge.ingest import enqueue_ingestion

		self.db_set("status", "Pending", update_modified=False)
		enqueue_ingestion(self.name)
