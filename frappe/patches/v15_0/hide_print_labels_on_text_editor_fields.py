import json

import frappe


def execute():
	filters = {
		"custom_format": 0,
		"raw_printing": 0,
		"standard": "No",
	}
	for name in frappe.get_all("Print Format", filters=filters, pluck="name"):
		doc = frappe.get_doc("Print Format", name)

		if doc.get("print_designer"):
			continue
		if not doc.get("format_data"):
			continue
		if not doc.get("doc_type"):
			continue

		patched = []
		try:
			meta = frappe.get_meta(doc.get("doc_type"))
			data = json.loads(doc.format_data)  # type: ignore

			assert isinstance(data, list)
			for d in data:
				assert isinstance(d, dict)
				if "nolabel" in d:
					continue  # Ignore already changed formats even if unlikely

				fieldname = d.get("fieldname")
				if not fieldname:
					continue

				if "address" in fieldname:
					continue  # We keep the label on address fields, reverting to the original intended behavior

				df = meta.get_field(fieldname)
				if not df:
					continue
				if df.fieldtype != "Text Editor":
					continue

				d["nolabel"] = 1
				patched.append(d)

			if patched:
				doc.db_set("format_data", json.dumps(data))
		except Exception as e:
			print(f"Could not patch Print Format {name!r}:", e)
