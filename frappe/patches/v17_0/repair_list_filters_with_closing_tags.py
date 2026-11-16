import json
import re

import frappe
from frappe.desk.doctype.list_filter.list_filter import compute_route_signature

TRAILING_CLOSING_TAGS = re.compile(r"(</[a-zA-Z][\w-]*>)+$")


def execute():
	"""The HTML sanitizer appended closing tags to saved filters holding a tag, breaking their JSON."""
	for name, reference_doctype, filters in frappe.get_all(
		"List Filter",
		filters={"filters": ["like", "%>"]},
		fields=["name", "reference_doctype", "filters"],
		as_list=True,
	):
		repaired = TRAILING_CLOSING_TAGS.sub("", filters)
		try:
			parsed = json.loads(repaired)
		except ValueError:
			continue

		frappe.db.set_value(
			"List Filter",
			name,
			{
				"filters": repaired,
				"route_signature": compute_route_signature(reference_doctype, parsed),
			},
			update_modified=False,
		)
