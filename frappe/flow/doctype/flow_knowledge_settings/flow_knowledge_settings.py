# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class FlowKnowledgeSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		chunk_overlap: DF.Int
		chunk_size: DF.Int
		embedding_dimension: DF.Int
		embedding_model: DF.Link | None
		search_type: DF.Literal["Hybrid", "Vector"]
	# end: auto-generated types

	def validate(self):
		self._validate_chunking()
		self._guard_model_change()
		self._sync_embedding_dimension()

	def _validate_chunking(self):
		if cint(self.chunk_size) < 1:
			frappe.throw(_("Chunk Size must be at least 1."), title=_("Invalid Chunking"))
		if cint(self.chunk_overlap) >= cint(self.chunk_size):
			frappe.throw(_("Chunk Overlap must be smaller than Chunk Size."), title=_("Invalid Chunking"))

	def on_update(self):
		if not (self.embedding_model and self.has_value_changed("embedding_model")):
			return
		from frappe.flow.knowledge import attachment_store
		from frappe.flow.knowledge.ingest import reembed_all

		# chat attachments are not embedded again: old chats lose search over them
		frappe.db.after_commit.add(attachment_store.drop_table)
		reembed_all()
		if frappe.db.exists("Flow Agent Memory", {"status": "Active"}):
			frappe.enqueue("frappe.flow.memory.store.ensure_table", queue="long", enqueue_after_commit=True)

	def _guard_model_change(self):
		"""Without a model, the chunks can't be embedded again."""
		previous = self.get_doc_before_save()
		removed = previous and previous.embedding_model and not self.embedding_model
		if not removed:
			return
		chunk_count = frappe.db.count("Flow Knowledge Chunk")
		if chunk_count:
			frappe.throw(
				_(
					"{0} knowledge chunks were embedded with the current model. Delete all knowledge sources before removing the embedding model."
				).format(chunk_count),
				title=_("Embedding Model In Use"),
			)

	def _sync_embedding_dimension(self):
		if not self.embedding_model:
			self.embedding_dimension = 0
			return
		previous = self.get_doc_before_save()
		model_unchanged = previous is not None and previous.embedding_model == self.embedding_model
		if model_unchanged and self.embedding_dimension:
			return

		from frappe.flow.knowledge.embedder import probe_dimension

		self.embedding_dimension = probe_dimension(self.embedding_model)


def embeddings_configured() -> bool:
	return bool(
		frappe.get_cached_value("Flow Knowledge Settings", "Flow Knowledge Settings", "embedding_model")
	)


def require_embedding_model():
	"""Knowledge ingestion needs an embedding model; block creating knowledge docs until one is set."""
	settings = frappe.get_cached_doc("Flow Knowledge Settings")
	if not settings.embedding_model:
		frappe.throw(
			_("Set an embedding model in Flow Knowledge Settings before adding knowledge bases or sources."),
			title=_("Flow Knowledge Settings Required"),
		)
