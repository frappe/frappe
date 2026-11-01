import frappe
from frappe.desk.doctype.form_layout.form_layout import (
	OMITTING_LAYOUT_TYPES,
	omitted_fieldnames,
	parse_layout,
	parse_omitted,
)


def execute():
	"""Write `omitted` on each Details and New Record row, as a save now does, keeping its entries."""
	rows = frappe.get_all(
		"Form Layout",
		filters={"type": ("in", OMITTING_LAYOUT_TYPES)},
		fields=["name", "dt", "layout", "omitted"],
	)
	for row in rows:
		if not frappe.db.exists("DocType", row.dt):
			continue
		try:
			kept = parse_omitted(row.omitted)
			fresh = omitted_fieldnames(row.dt, parse_layout(row.layout))
		except Exception:
			# One unreadable row must not stop the migrate; it keeps the `omitted` it has.
			frappe.log_error(f"Could not fill omitted for Form Layout {row.name}")
			continue
		omitted = kept + [fieldname for fieldname in fresh if fieldname not in kept]
		frappe.db.set_value(
			"Form Layout", row.name, "omitted", frappe.as_json(omitted), update_modified=False
		)
