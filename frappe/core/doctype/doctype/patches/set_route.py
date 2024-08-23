import frappe
from frappe.desk.utils import slug


def execute():
	for doctype in frappe.get_all("DocType", ["name", "route"], dict(istable=0)):
		if not doctype.route:
			frappe.db.set_value("DocType", doctype.name, "route", slug(doctype.name), update_modified=False)
