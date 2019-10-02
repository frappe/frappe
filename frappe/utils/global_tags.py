# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def delete_tags_for_document(doc):
	"""
		Delete the __global_tags entry of a document that has
		been deleted
		:param doc: Deleted document
	"""
	if not frappe.db.table_exists("Tag Link"):
		return

	frappe.db.sql("""DELETE FROM `tabTag Link` WHERE `dt`=%s AND `dn`=%s""", (doc.doctype, doc.name))

def update_global_tags(doc, tags):
	"""
		Adds tags for documents
		:param doc: Document to be added to global tags
	"""

	new_tags = list(set([tag.strip() for tag in tags.split(",") if tag]))

	for tag in new_tags:
		if not frappe.db.exists("Tag Link", {"parenttype": doc.doctype, "parent": doc.name, "tag": tag}):
			frappe.get_doc({
				"doctype": "Tag Link",
				"dt": doc.doctype,
				"dn": doc.name,
				"parenttype": doc.doctype,
				"parent": doc.name,
				"title": doc.get_title() or '',
				"tag": tag
			}).insert(ignore_permissions=True)

	existing_tags = [tag.tag for tag in frappe.get_list("Tag Link", filters={"dt": doc.doctype, "dn": doc.name}, fields=["tag"])]

	deleted_tags = get_deleted_tags(new_tags, existing_tags)

	if deleted_tags:
		for tag in deleted_tags:
			delete_tag_for_document(doc.doctype, doc.name, tag)

def get_deleted_tags(new_tags, existing_tags):

	return list(set(existing_tags) - set(new_tags))

def delete_tag_for_document(dt, dn, tag):
	frappe.db.sql("""DELETE FROM `tabTag Link` WHERE dt=%s, dn=%s, tag=%s""", (dt, dn, tag))

@frappe.whitelist()
def get_documents_for_tag(tag):
	"""
		Search for given text in __global_tags
		:param tag: tag to be searched
	"""
	# remove hastag `#` from tag
	tag = tag[1:]
	results = []

	result = frappe.db.sql("""
			SELECT `dt`, `dn`, `title`, `tag`
			FROM `tabTag Link`
			WHERE `tag`=%s
		""", (tag), as_dict=True)

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