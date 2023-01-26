import frappe
from frappe.model.naming import append_number_if_name_exists
from frappe.utils.dashboard import get_dashboards_with_link


def execute():
	if (
		not frappe.db.table_exists("Dashboard Chart")
		or not frappe.db.table_exists("Number Card")
		or not frappe.db.table_exists("Dashboard")
	):
		return

	frappe.reload_doc("desk", "doctype", "dashboard_chart")
	frappe.reload_doc("desk", "doctype", "number_card")
	frappe.reload_doc("desk", "doctype", "dashboard")

	modified_charts = get_modified_docs("Dashboard Chart")
	modified_cards = get_modified_docs("Number Card")
	modified_dashboards = [doc.name for doc in get_modified_docs("Dashboard")]

	for chart in modified_charts:
		modified_dashboards += get_dashboards_with_link(chart.name, "Dashboard Chart")
		rename_modified_doc(chart.name, "Dashboard Chart")

	for card in modified_cards:
		modified_dashboards += get_dashboards_with_link(card.name, "Number Card")
		rename_modified_doc(card.name, "Number Card")

	modified_dashboards = list(set(modified_dashboards))

	for dashboard in modified_dashboards:
		rename_modified_doc(dashboard, "Dashboard")


def get_modified_docs(doctype):
	return frappe.get_all(
		doctype, filters={"owner": "Administrator", "modified_by": ["!=", "Administrator"]}
	)


def rename_modified_doc(docname, doctype):
	new_name = docname + " Custom"
	try:
		frappe.rename_doc(doctype, docname, new_name)
	except frappe.ValidationError:
		new_name = append_number_if_name_exists(doctype, new_name)
		frappe.rename_doc(doctype, docname, new_name)
