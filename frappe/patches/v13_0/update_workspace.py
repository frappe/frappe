import frappe
import json
from frappe import _

def execute():
	frappe.reload_doc('desk', 'doctype', 'workspace', force=True)
	order_by = "is_standard asc, pin_to_top desc, pin_to_bottom asc, name asc"
	for seq, wspace in enumerate(frappe.get_all('Workspace', order_by=order_by)):
		doc = frappe.get_doc('Workspace', wspace.name)
		content = create_content(doc)
		create_wspace_copy(doc, seq, content)
	frappe.db.commit()

def create_content(doc):
	content = []
	if doc.charts:
		for c in doc.charts:
			content.append({"type":"chart","data":{"chart_name":c.label,"col":12,"pt":0,"pr":0,"pb":0,"pl":0}})
	if doc.shortcuts:
		content.append({"type":"spacer","data":{"col":12,"pt":0,"pr":0,"pb":0,"pl":0}})
		content.append({"type":"header","data":{"text":doc.shortcuts_label or _("Your Shortcuts"),"level":4,"col":12,"pt":0,"pr":0,"pb":0,"pl":0}})
		for s in doc.shortcuts:
			content.append({"type":"shortcut","data":{"shortcut_name":s.label,"col":4,"pt":0,"pr":0,"pb":0,"pl":0}})
	if doc.links:
		content.append({"type":"spacer","data":{"col":12,"pt":0,"pr":0,"pb":0,"pl":0}})
		content.append({"type":"header","data":{"text":doc.cards_label or _("Reports & Masters"),"level":4,"col":12,"pt":0,"pr":0,"pb":0,"pl":0}})
		for l in doc.links:
			if l.type == 'Card Break':
				content.append({"type":"card","data":{"card_name":l.label,"col":4,"pt":0,"pr":0,"pb":0,"pl":0}})
	return content

def create_wspace_copy(doc, seq, content):
	new_doc = frappe.new_doc('Workspace')
	new_doc.content = json.dumps(content)
	new_doc.sequence_id = seq + 1
	new_doc.charts = doc.charts or []
	new_doc.shortcuts = doc.shortcuts or []
	new_doc.links = doc.links or []
	new_doc.label = doc.label
	new_doc.icon = doc.icon
	if doc.is_standard:
		new_doc.public = 1
		new_doc.title = doc.label
	else:
		new_doc.for_user = doc.for_user
		new_doc.title = doc.extends
	doc.delete()
	new_doc.insert()