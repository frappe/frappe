# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from flow.utils.system_generated import block_delete, validate_immutable

REQUIRED_INPUT = {
	"Text": "content",
	"File": "file",
	"URL": "url",
	"DocType": "reference_doctype",
}


class FlowKnowledgeSource(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		auto_sync: DF.Check
		chunk_count: DF.Int
		chunk_overlap: DF.Int
		chunk_size: DF.Int
		content: DF.LongText | None
		content_fields: DF.SmallText | None
		error_log: DF.LongText | None
		file: DF.Attach | None
		filters: DF.JSON | None
		is_system_generated: DF.Check
		knowledge_base: DF.Link
		last_synced_at: DF.Datetime | None
		reference_doctype: DF.Link | None
		source_type: DF.Literal["Text", "File", "URL", "DocType"]
		status: DF.Literal["Pending", "Processing", "Completed", "Failed"]
		title: DF.Data
		url: DF.Data | None
	# end: auto-generated types

	def validate(self):
		if self.is_new():
			from flow.flow.doctype.flow_knowledge_settings.flow_knowledge_settings import (
				require_embedding_model,
			)

			require_embedding_model()
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
		self._validate_chunking()
		validate_immutable(self, ("source_type", "knowledge_base"))

	def _validate_chunking(self):
		"""0 inherits the global default. Only validate values set on the source itself."""
		if self.chunk_size and self.chunk_overlap and cint(self.chunk_overlap) >= cint(self.chunk_size):
			frappe.throw(_("Chunk Overlap must be smaller than Chunk Size."), title=_("Invalid Chunking"))

	def after_insert(self):
		if self.flags.skip_auto_ingest:
			return
		from flow.knowledge.ingest import enqueue_ingestion

		enqueue_ingestion(self.name)

	def on_trash(self):
		block_delete(self)
		from flow.knowledge.ingest import purge_source

		purge_source(self.name)

	@frappe.whitelist()
	def resync(self, rebuild: bool = False):
		"""rebuild forces a full re-chunk; used when chunk settings change and the
		existing chunks are stale."""
		from flow.knowledge.ingest import enqueue_ingestion

		self.db_set("status", "Pending", update_modified=False)
		enqueue_ingestion(self.name, rebuild=bool(rebuild))

	@frappe.whitelist()
	def reconcile(self):
		from flow.knowledge.ingest import enqueue_reconciliation

		enqueue_reconciliation(self.name)
