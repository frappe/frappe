# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def reset():
	"""
	Deletes all data in `tabTag Link`
	:return:
	"""
	frappe.db.sql('DELETE FROM `tabTag Link`')

def delete_tags_for_document(doc):
	"""
		Delete the __global_tags entry of a document that has
		been deleted
		:param doc: Deleted document
	"""
	frappe.db.sql("""DELETE
		FROM `tabTag Link`
		WHERE dt = %s
			AND dn = %s""", (doc.doctype, doc.name))

def update_global_tags(doc, tags):
	"""
		Adds tags for documents
		:param doc: Document to be added to global tags
	"""
	if frappe.local.conf.get('disable_global_tags') or not doc.get("_user_tags"):
		return

	if not frappe.db.exists("Tag Link", {"dt": doc.doctype, "dn": doc.name}):
		frappe.get_doc({
			"doctype": "Tag Link",
			"dt": doc.doctype,
			"dn": doc.name,
			"title": doc.get_title() or '',
			"tags": tags
		}).insert(ignore_permissions=True)
	else:
		frappe.db.set_value("Tag Link", {"dt": doc.doctype, "dn": doc.name}, "tags", tags)

@frappe.whitelist()
def get_documents_for_tag(tag):
	"""
		Search for given text in __global_tags
		:param tag: tag to be searched
	"""
	# remove hastag `#` from tag
	tag = tag[1:]

	results = []

	tag = frappe.db.escape('%{0}%'.format(tag.lower()), False)

	result = frappe.db.sql('''
			SELECT `dt`, `dn`, `title`, `tags`
			FROM `tabTag Link`
			WHERE `tags` LIKE {0}
		'''.format(tag), as_dict=True)

	for res in result:
		results.append({
			"doctype": res.dt,
			"name": res.dn,
			"content": res.title
		})

	return results

@frappe.whitelist()
def get_tags_list_for_awesomebar():
	return [t.name for t in frappe.get_list("Tag")]