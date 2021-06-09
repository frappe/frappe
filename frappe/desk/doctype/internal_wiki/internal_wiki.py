# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.desk.desktop import save_new_widget
from frappe.desk.doctype.internal_wiki_page.internal_wiki_page import new_internal_wiki_page, delete_page, sort_page
from frappe.model.document import Document

class InternalWiki(Document):
	pass

@frappe.whitelist()
def get_wiki_pages():
	has_access = ("System Manager" in frappe.get_roles())

	default_pages = frappe.get_doc("Internal Wiki", "Default").wiki_pages
	pages = prepare_pages(default_pages)
	if not frappe.db.exists("Internal Wiki", frappe.session.user):
		return {"pages": pages, "has_access": has_access}

	user_pages = frappe.get_doc("Internal Wiki", frappe.session.user).wiki_pages
	user_pages = prepare_pages(user_pages, True)
	pages.extend(user_pages)

	return {"pages": pages, "has_access": has_access}

def prepare_pages(pages, is_editable=False):
	prepared_pages = [] 
	for p in pages:
		page = {
			"title": p.title,
			"icon": p.icon,
			"parent_wiki": p.parent,
			"parent_page": p.parent_page,
			"content": p.content,
			"is_editable": is_editable or ("System Manager" in frappe.get_roles())
		}
		prepared_pages.append(page)
	return prepared_pages

@frappe.whitelist()
def save_wiki_page(title, parent, public, sb_items, deleted_pages, new_widgets, blocks, save=True):
	if save: 
		# Create Workspace if not exist
		if not frappe.db.exists("Workspace", title):
			wspace = frappe.new_doc('Workspace')
			wspace.label = title
			wspace.for_wiki = 1
			wspace.insert(ignore_permissions=True)

		# create new Internal Wiki Page
		new_doc = new_internal_wiki_page(title, blocks, parent, 'wiki_pages')

		if public:
			doc = frappe.get_doc("Internal Wiki", "Default")
			doc.wiki_pages.extend([new_doc])
		elif not frappe.db.exists("Internal Wiki", frappe.session.user):
			doc = frappe.new_doc("Internal Wiki")
			doc.title = frappe.session.user
			doc.wiki_pages = [new_doc]
		else:
			doc = frappe.get_doc("Internal Wiki", frappe.session.user)
			doc.wiki_pages.extend([new_doc])
		doc.save(ignore_permissions=True)
	else:
		for page in ["Default", frappe.session.user]:
			if frappe.db.exists("Internal Wiki", page):
				doc = frappe.get_doc("Internal Wiki", page)
				for d in doc.wiki_pages:
					if d.title == title:
						d.content = blocks
						break
				doc.save(ignore_permissions=True)

	if json.loads(deleted_pages):
		return delete_pages(json.loads(deleted_pages))

	if json.loads(sb_items):
		sort_pages(json.loads(sb_items))

	if json.loads(new_widgets):
		save_new_widget(title, blocks, new_widgets, public)

	return title

def delete_pages(deleted_pages):
	for page in deleted_pages:
		# delete default Internal Wiki Page
		if "System Manager" in frappe.get_roles():
			delete_page("Default", page)

		# delete user's Internal Wiki Page
		if frappe.db.exists("Internal Wiki", frappe.session.user):
			delete_page(frappe.session.user, page)

		# delete Workspace
		filters = {
			'extends': page.get("title"),
			'for_user': frappe.session.user,
			'for_wiki': 1
		}
		pages = frappe.get_list("Workspace", filters=filters)
		if pages:
			frappe.get_doc("Workspace", pages[0]).delete()
	return 'Home'

def sort_pages(sb_items):
	# update the index of default Internal Wiki Pages based on sorted sidebar pages
	if "System Manager" in frappe.get_roles():
		sort_page("Default", sb_items)

	# update the index of user's Internal Wiki Pages based on sorted sidebar pages
	if frappe.db.exists("Internal Wiki", frappe.session.user):
		sort_page(frappe.session.user, sb_items)