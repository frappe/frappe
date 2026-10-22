# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Code-first knowledge API.

Build and populate a Flow Knowledge Base from Python — attach text, files, URLs,
or DocType data without the desk UI. Ingestion is synchronous: when an add_*
call returns, the content is embedded, indexed, and ready to search.
"""

from __future__ import annotations

import frappe
from frappe import _

KB_DOCTYPE = "Flow Knowledge Base"
SOURCE_DOCTYPE = "Flow Knowledge Source"
_TITLE_LIMIT = 140


class Knowledge:
	"""A handle to a named Flow Knowledge Base. Construction is get-or-create by title."""

	def __init__(self, title: str, *, description: str | None = None) -> None:
		self.name = _ensure_kb(title, description)

	def add_text(self, content: str, *, title: str | None = None) -> str:
		return self._ingest(source_type="Text", title=title or _snippet(content), content=content)

	def add_file(self, file_url: str, *, title: str | None = None) -> str:
		return self._ingest(source_type="File", title=title or file_url, file=file_url)

	def add_local_file(self, path: str, *, title: str | None = None) -> str:
		import os

		from flow.knowledge.extract import _extract_by_extension

		extension = os.path.splitext(path)[1].lower().lstrip(".")
		with open(path, "rb") as handle:
			text = _extract_by_extension(handle.read(), extension)
		return self.add_text(text, title=title or os.path.basename(path))

	def add_url(self, url: str, *, title: str | None = None) -> str:
		return self._ingest(source_type="URL", title=title or url, url=url)

	def add_doctype(
		self,
		reference_doctype: str,
		*,
		content_fields: list[str],
		filters: dict | None = None,
		title: str | None = None,
		auto_sync: bool = False,
	) -> str:
		return self._ingest(
			source_type="DocType",
			title=title or reference_doctype,
			reference_doctype=reference_doctype,
			content_fields=", ".join(content_fields),
			filters=frappe.as_json(filters) if filters else None,
			auto_sync=int(auto_sync),
		)

	def _ingest(self, **fields: object) -> str:
		from flow.knowledge.ingest import ingest_source

		source = frappe.get_doc({"doctype": SOURCE_DOCTYPE, "knowledge_base": self.name, **fields})
		source.flags.skip_auto_ingest = True
		source.insert()
		ingest_source(source.name)
		return source.name


def _ensure_kb(title: str, description: str | None) -> str:
	title = (title or "").strip()
	if not title:
		frappe.throw(_("Knowledge base title is required."), title=_("Invalid Knowledge Base"))
	if frappe.db.exists(KB_DOCTYPE, title):
		return title
	return frappe.get_doc({"doctype": KB_DOCTYPE, "title": title, "description": description}).insert().name


def _snippet(content: str) -> str:
	text = " ".join((content or "").split())
	return text[:_TITLE_LIMIT] or "Text"
