import json

import frappe


def execute():
	reports_data = frappe.get_all(
		"Report",
		filters={
			"json": ["not like", '%%%"order_by": "`tab%%%'],
			"report_type": "Report Builder",
			"is_standard": "No",
		},
		fields=["name"],
	)

	for d in reports_data:
		doc = frappe.get_doc("Report", d.get("name"))

		if not doc.get("json"):
			continue

		json_data = json.loads(doc.get("json"))

		parts = []
		if ("order_by" in json_data) and ("." in json_data.get("order_by")):
			parts = json_data.get("order_by").split(".")

			sort_by = parts[1].split(" ")

			json_data["order_by"] = f"`tab{doc.ref_doctype}`.`{sort_by[0]}`"
			json_data["order_by"] += f" {sort_by[1]}" if len(sort_by) > 1 else ""

			doc.json = json.dumps(json_data)
			doc.save()
