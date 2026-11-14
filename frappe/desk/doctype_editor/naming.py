# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.desk.doctype_editor.mode import check_mode, design_refusal
from frappe.utils import cint

MAX_PREFIXES = 50


@frappe.desk_v2_only
@frappe.whitelist(methods=["GET"])
def get_series_counters(doctype: str, mode: str, prefixes: str | list[str]) -> dict[str, int]:
	"""Each series prefix's last number, so the editor can show the next name. Reads; never moves a counter."""
	check_reader(doctype, mode)
	prefixes = frappe.parse_json(prefixes)
	if not isinstance(prefixes, list) or not all(isinstance(prefix, str) for prefix in prefixes):
		frappe.throw(_("Send the series prefixes as a list of text."))
	if len(prefixes) > MAX_PREFIXES:
		frappe.throw(_("Ask for at most {0} series at a time.").format(MAX_PREFIXES))
	current = series_values(prefixes)
	return {prefix: cint(current.get(prefix)) for prefix in prefixes}


def check_reader(doctype: str, mode: str) -> None:
	"""A DocType not yet created needs only Design rights on a custom DocType."""
	if frappe.db.exists("DocType", doctype):
		return check_mode(doctype, mode)
	if mode != "Design":
		frappe.throw(_("A DocType not yet created opens only in Design mode."))
	if refusal := design_refusal(custom=True):
		frappe.throw(refusal, frappe.PermissionError)


def series_values(prefixes: list[str]) -> dict[str, int]:
	if not prefixes:
		return {}
	series = frappe.qb.Table("tabSeries")
	query = frappe.qb.from_(series).select(series.name, series.current).where(series.name.isin(prefixes))
	return dict(query.run())
