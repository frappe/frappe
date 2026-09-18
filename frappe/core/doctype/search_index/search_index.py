# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SearchIndex(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		enabled: DF.Check
		index_size: DF.Data | None
		indexed_documents: DF.Int
		last_built_on: DF.Datetime | None
		search_class: DF.Data
		status: DF.Literal["Not Built", "Building", "Ready", "Needs Rebuild"]
	# end: auto-generated types

	def on_update(self):
		"""Start building as soon as it is switched on, rather than at the next scheduled pass."""
		before = self.get_doc_before_save()
		if self.enabled and not (before and before.enabled):
			self.enqueue_build()

	def enqueue_build(self):
		"""Queue after the commit: the job reads this record, and would find the older value."""
		from frappe.search.sqlite_search import build_index

		frappe.enqueue(
			build_index,
			queue="long",
			job_id=self.search_class,
			deduplicate=True,
			enqueue_after_commit=True,
			timeout=2 * 60 * 60,
			search_class_path=self.search_class,
			force=True,
		)

	def record_build(self, document_count: int, size_in_bytes: int):
		"""Note what the finished index holds, so its state is visible without opening the file."""
		self.db_set(
			{
				"status": "Ready",
				"indexed_documents": document_count,
				"index_size": format_size(size_in_bytes),
				"last_built_on": frappe.utils.now_datetime(),
			},
			update_modified=False,
			commit=True,
		)


def format_size(size_in_bytes: int) -> str:
	size = float(size_in_bytes)
	for unit in ("B", "KB", "MB", "GB"):
		if size < 1024 or unit == "GB":
			return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
		size /= 1024

	return f"{size:.1f} GB"


@frappe.whitelist()
def rebuild(doc: str):
	"""Rebuild this index from scratch."""
	index = frappe.get_doc("Search Index", frappe.parse_json(doc).get("name"))
	index.check_permission("write")
	index.db_set("status", "Building", update_modified=False)
	index.enqueue_build()


def sync_search_indexes():
	"""Give every registered search class a record, the way scheduled jobs get one."""
	from frappe.search.sqlite_search import get_search_classes

	for SearchClass in get_search_classes():
		search_class = f"{SearchClass.__module__}.{SearchClass.__name__}"
		if frappe.db.exists("Search Index", search_class):
			continue

		frappe.get_doc(
			doctype="Search Index",
			search_class=search_class,
			enabled=int(SearchClass.ENABLED_BY_DEFAULT),
		).insert()
