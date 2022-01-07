import json
from difflib import unified_diff
from typing import List

import frappe
from frappe.utils import pretty_date


@frappe.whitelist()
def get_version_diff(
	from_version: str, to_version: str, fieldname: str = "script"
) -> List[str]:

	before, before_timestamp = _get_value_from_version(from_version, fieldname)
	after, after_timestamp = _get_value_from_version(to_version, fieldname)

	if not (before and after):
		return ["Values not available for diff"]

	before = before.split("\n")
	after = after.split("\n")

	diff = unified_diff(
		before,
		after,
		fromfile=from_version,
		tofile=to_version,
		fromfiledate=before_timestamp,
		tofiledate=after_timestamp,
	)
	return list(diff)


def _get_value_from_version(version_name: str, fieldname: str):
	version = frappe.get_list(
		"Version", fields=["data", "modified"], filters={"name": version_name}
	)
	if version:
		data = json.loads(version[0].data)
		changed_fields = data.get("changed", [])

		# data structure of field: [fieldname, before_save, after_save]
		for field in changed_fields:
			if field[0] == fieldname:
				return field[2], str(version[0].modified)

	return None, None


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def version_query(doctype, txt, searchfield, start, page_len, filters):
	results = frappe.get_list(
		"Version",
		fields=["name", "modified"],
		filters=filters,
		limit_start=start,
		limit_page_length=page_len,
		order_by="modified desc",
	)
	return [(d.name, pretty_date(d.modified), d.modified) for d in results]
