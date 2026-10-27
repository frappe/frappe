# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""The command palette's server side."""

from urllib.parse import urlsplit

import frappe
from frappe.desk.doctype.global_search_settings.global_search_settings import (
	get_doctypes_for_global_search,
)
from frappe.desk.search import build_for_autosuggest, search_widget
from frappe.utils import get_url_to_form

RECORDS_PER_DOCTYPE = 3
RECORDS_IN_ALL = 10
SHORTEST_QUERY = 2


@frappe.whitelist(methods=["GET"])
def search_records(txt: str, doctype: str | None = None) -> list[dict]:
	"""Up to 10 records matching `txt`, 3 per readable doctype, any named exactly `txt` first."""
	txt = txt.strip()
	if len(txt) < SHORTEST_QUERY:
		return []

	found = [row for each in searchable_doctypes(doctype) for row in records_of(each, txt)]
	# stable, so the rest keep their doctype order
	found.sort(key=lambda row: not is_exact(row["name"], txt))
	return found[:RECORDS_IN_ALL]


def searchable_doctypes(current: str | None) -> list[str]:
	"""The current page's doctype, then the Global Search doctypes in their order, all readable."""
	readable = set(frappe.get_user().get_can_read())
	listed = get_doctypes_for_global_search()
	wanted = dict.fromkeys([current, *listed] if current else listed)
	return [doctype for doctype in wanted if doctype in readable and has_rows(doctype)]


def has_rows(doctype: str) -> bool:
	meta = frappe.get_meta(doctype)
	return not (meta.issingle or meta.istable or meta.is_virtual)


def records_of(doctype: str, txt: str) -> list[dict]:
	"""Labelled as a Link field shows them, with the address in its own app's prefix."""
	results = search_widget(doctype, txt, page_length=RECORDS_PER_DOCTYPE)
	if len(results) == RECORDS_PER_DOCTYPE and not any(is_exact(row[0], txt) for row in results):
		# a prefix match ties with the exact name, so a full page may have left it out
		named = search_widget(doctype, txt, filters={"name": ["like", escape_like(txt)]}, page_length=1)
		results = [*(row for row in named if is_exact(row[0], txt)), *results][:RECORDS_PER_DOCTYPE]
	return [
		{
			"doctype": doctype,
			"name": row["value"],
			"label": row.get("label") or row["value"],
			"route": record_path(doctype, row["value"]),
		}
		for row in build_for_autosuggest(results, doctype=doctype)
	]


def record_path(doctype: str, name: str) -> str:
	"""The record's address, path only, so it opens on the host the search was made from."""
	return urlsplit(get_url_to_form(doctype, name)).path


def escape_like(txt: str) -> str:
	return txt.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def is_exact(name, txt: str) -> bool:
	return str(name).casefold() == txt.casefold()
