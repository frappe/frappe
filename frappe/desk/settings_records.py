# SETTINGS RECORDS — the stored `Settings Dialog` records with their pane and block rows, for the rules.

import frappe
from frappe.desk.doctype.rail.rail import SITE_LAYER


def shipped_records(host: str | None = None, exclude: str | None = None) -> list:
	"""Every app-layer record, or the ones in this host's panes, each holding its `panes` and `blocks` rows."""
	filters = {"standard": 1, "user": SITE_LAYER}
	if exclude:
		filters["name"] = ("!=", exclude)

	records = frappe.get_all(
		"Settings Dialog",
		filters=filters,
		or_filters={"extends": host, "app": host} if host else None,
		fields=["name", "app", "extends"],
	)
	if host:
		records = [record for record in records if (record.extends or record.app) == host]

	for record in records:
		record.panes, record.blocks = [], []

	by_name = {record.name: record for record in records}
	for doctype, attribute in (("Settings Pane", "panes"), ("Settings Block", "blocks")):
		for row in _rows(doctype, list(by_name)):
			getattr(by_name[row.parent], attribute).append(row)

	return records


def _rows(doctype: str, parents: list[str]) -> list:
	if not parents:
		return []

	return frappe.get_all(
		doctype,
		filters={"parenttype": "Settings Dialog", "parent": ("in", parents)},
		fields=["*"],
		order_by="parent asc, idx asc",
	)
