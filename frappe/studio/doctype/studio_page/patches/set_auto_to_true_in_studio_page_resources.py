import frappe


def execute():
	frappe.qb.update("Studio Page Resource").set("auto", 1).run()
