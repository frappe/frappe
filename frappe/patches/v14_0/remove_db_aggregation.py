import re

import frappe
from frappe.query_builder import DocType


def execute():
	"""Replace temporarily available Database Aggregate APIs on frappe (develop)

	APIs changed:
	        * frappe.db.max => frappe.qb.max
	        * frappe.db.min => frappe.qb.min
	        * frappe.db.sum => frappe.qb.sum
	        * frappe.db.avg => frappe.qb.avg
	"""
	ServerScript = DocType("Server Script")
	server_scripts = (
		frappe.qb.from_(ServerScript)
		.where(
			ServerScript.script.like("%frappe.db.max(%")
			| ServerScript.script.like("%frappe.db.min(%")
			| ServerScript.script.like("%frappe.db.sum(%")
			| ServerScript.script.like("%frappe.db.avg(%")
		)
		.select("name", "script")
		.run(as_dict=True)
	)

	for server_script in server_scripts:
		name, script = server_script["name"], server_script["script"]

		for agg in ["avg", "max", "min", "sum"]:
			script = re.sub(f"frappe.db.{agg}\\(", f"frappe.qb.{agg}(", script)

		frappe.db.update("Server Script", name, "script", script)
