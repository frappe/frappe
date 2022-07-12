from multiprocessing.sharedctypes import Value
import frappe
import json


def execute():
	for doctype in frappe.get_list("DocType", filters={"istable": 0, "issingle": 0}):
		if not frappe.db.has_table(doctype.name):
			continue

		if frappe.db.has_column(doctype.name, "_user_tags"):
			# Ensure _user_tags is a valid json string
			for record in frappe.db.get_all(doctype.name, filters=[("_user_tags", "is", "set")], fields=["name", "_user_tags"]):
				try:
					tags = json.loads(record["_user_tags"])
				except ValueError:
					tags = [tag for tag in record["_user_tags"].split(",") if tag]
					frappe.db.set_value(doctype.name, record["name"], "_user_tags", json.dumps(tags))


		if frappe.db.has_column(doctype.name, "_user_tags") or frappe.db.has_column(doctype.name, "_assign"):
			# Migrate to JSON fields
			frappe.db.updatedb(doctype.name)



