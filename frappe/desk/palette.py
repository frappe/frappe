# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""The command palette's server side."""

from urllib.parse import urlsplit

import frappe
from frappe import _
from frappe.desk.doctype.global_search_settings.global_search_settings import (
	get_doctypes_for_global_search,
)
from frappe.desk.search import search_widget
from frappe.utils import cstr, get_url_to_form, strip_html_tags
from frappe.utils.html_utils import unescape_html

RECORDS_PER_DOCTYPE = 3
RECORDS_IN_ALL = 10
SHORTEST_QUERY = 2
RICH_TEXT = {"Text Editor", "HTML Editor"}


@frappe.whitelist(methods=["GET"])
def search_records(txt: str, doctype: str | None = None) -> list[dict]:
	"""Up to 10 records matching `txt`, 3 per readable doctype, any named exactly `txt` first."""
	txt = txt.strip()
	if len(txt) < SHORTEST_QUERY:
		return []

	found = [row for each in searchable_doctypes(doctype) for row in records_of(each, txt)]
	return exact_first(found, txt)[:RECORDS_IN_ALL]


@frappe.whitelist(methods=["GET"])
def search_doctype_records(doctype: str, txt: str) -> list[dict]:
	"""Up to 10 records of one readable doctype matching `txt`, any named exactly `txt` first."""
	txt = txt.strip()
	if len(txt) < SHORTEST_QUERY or not is_searchable(doctype):
		return []

	return exact_first(records_of(doctype, txt, RECORDS_IN_ALL), txt)


def exact_first(found: list[dict], txt: str) -> list[dict]:
	# stable, so the rest keep their doctype order
	return sorted(found, key=lambda row: not is_exact(row["name"], txt))


def searchable_doctypes(current: str | None) -> list[str]:
	"""The current page's doctype, then the Global Search doctypes in their order, all readable."""
	readable = set(frappe.get_user().get_can_read())
	listed = get_doctypes_for_global_search()
	wanted = dict.fromkeys([current, *listed] if current else listed)
	return [doctype for doctype in wanted if doctype in readable and has_rows(doctype)]


def is_searchable(doctype: str) -> bool:
	return doctype in frappe.get_user().get_can_read() and has_rows(doctype)


def has_rows(doctype: str) -> bool:
	meta = frappe.get_meta(doctype)
	return not (meta.issingle or meta.istable or meta.is_virtual)


def records_of(doctype: str, txt: str, limit: int = RECORDS_PER_DOCTYPE) -> list[dict]:
	"""Titled by the title field, whatever Link fields show, with the address in its own app's prefix."""
	results = search_widget(doctype, txt, page_length=limit, as_dict=True)
	if len(results) == limit and not any(is_exact(row.name, txt) for row in results):
		# a prefix match ties with the exact name, so a full page may have left it out
		named = search_widget(
			doctype, txt, filters={"name": ["like", escape_like(txt)]}, page_length=1, as_dict=True
		)
		results = [*(row for row in named if is_exact(row.name, txt)), *results][:limit]
	title = RecordTitle(doctype)
	return [
		{
			"doctype": doctype,
			"name": row.name,
			"label": title.of(row),
			"route": record_path(doctype, row.name),
		}
		for row in results
	]


class RecordTitle:
	"""A record's title field value, or its name where the doctype has none or it is empty."""

	def __init__(self, doctype: str):
		self.meta = frappe.get_meta(doctype)
		self.field = self.meta.get_field(self.meta.title_field) if self.meta.title_field else None

	def of(self, row: dict) -> str:
		if not self.field:
			value = None
		elif self.field.is_virtual:
			value = frappe.get_doc(self.meta.name, row.name).get_virtual_field_value(self.field)
		elif self.field.fieldtype in RICH_TEXT:
			value = unescape_html(strip_html_tags(cstr(row.get(self.field.fieldname))))
		else:
			value = row.get(self.field.fieldname)
		title = cstr(value).strip() or cstr(row.name)
		return _(title) if self.meta.translated_doctype else title


def record_path(doctype: str, name: str) -> str:
	"""The record's address, path only, so it opens on the host the search was made from."""
	return urlsplit(get_url_to_form(doctype, name)).path


def escape_like(txt: str) -> str:
	return txt.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def is_exact(name, txt: str) -> bool:
	return str(name).casefold() == txt.casefold()
