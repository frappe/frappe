import frappe
from six import string_types
from json import loads
from frappe.desk.doctype.workspace.workspace import get_link_type, get_report_type

def execute():
	if not frappe.db.exists("Doctype", "Desk Card"):
		return

	frappe.reload_doc('desk', 'doctype', 'workspace')

	pages = frappe.get_all("Workspace", filters={"is_standard": 0}, pluck="name")

	for page in pages:
		rebuild_links(page)

	frappe.delete_doc("DocType", "Desk Card")

def rebuild_links(page):
	# Empty links table

	doc = frappe.get_doc("Workspace", page)
	doc.links = []
	for card in get_all_cards(page):
		if isinstance(card.links, string_types):
			links = loads(card.links)
		else:
			links = card.links

		doc.append('links', {
			"label": card.label,
			"type": "Card Break",
			"icon": card.icon,
			"hidden": card.hidden or False
		})

		for link in links:
			doc.append('links', {
				"label": link.get('label') or link.get('name'),
				"type": "Link",
				"link_type": get_link_type(link.get('type')),
				"link_to": link.get('name'),
				"onboard": link.get('onboard'),
				"dependencies": ', '.join(link.get('dependencies', [])),
				"is_query_report": get_report_type(link.get('name')) if link.get('type').lower() == "report" else 0
			})

		doc.save(ignore_permissions=True)

def get_all_cards(page):
	return frappe.db.get_all("Desk Card", filters={"parent": page}, fields=['*'], order_by="idx")