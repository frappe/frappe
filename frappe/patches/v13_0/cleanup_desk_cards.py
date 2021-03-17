import frappe
from six import string_types
from json import loads
from frappe.desk.doctype.workspace.workspace import get_link_type, get_report_type

def execute():
	frappe.reload_doc('desk', 'doctype', 'workspace')
	
	pages = frappe.db.sql("Select `name` from `tabDesk Page`")
	# pages = frappe.get_all("Workspace", filters={"is_standard": 0}, pluck="name")

	for page in pages:
		rebuild_links(page[0])

	frappe.delete_doc("DocType", "Desk Card")

def rebuild_links(page):
	# Empty links table

	try:
		doc = frappe.get_doc("Workspace", page)
	except frappe.DoesNotExistError:
		db_doc = get_doc_from_db(page)
		
		doc = frappe.get_doc(db_doc)
		doc.insert(ignore_permissions=True)
	
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
			if not frappe.db.exists(get_link_type(link.get('type')), link.get('name')):
				continue
			
			doc.append('links', {
				"label": link.get('label') or link.get('name'),
				"type": "Link",
				"link_type": get_link_type(link.get('type')),
				"link_to": link.get('name'),
				"onboard": link.get('onboard'),
				"dependencies": ', '.join(link.get('dependencies', [])),
				"is_query_report": get_report_type(link.get('name')) if link.get('type').lower() == "report" else 0
			})
		
		try:
			doc.save(ignore_permissions=True)
		except frappe.LinkValidationError:
			print(doc.as_dict())

def get_doc_from_db(page):
	result = frappe.db.sql("SELECT * FROM `tabDesk Page` WHERE name=%s", [page],  as_dict=True)
	if result:
		return result[0].update({"doctype": "Workspace"})

def get_all_cards(page):
	return frappe.db.get_all("Desk Card", filters={"parent": page}, fields=['*'], order_by="idx")