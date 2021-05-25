# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.desk.desktop import save_new_widget
from frappe.model.document import Document

class InternalWikiPage(Document):

	def before_insert(self):
		if frappe.db.count('Internal Wiki Page') == 0:
			self.sequence_id = 1
		else:
			self.sequence_id = frappe.get_last_doc('Internal Wiki Page').sequence_id + 1

@frappe.whitelist()
def save_wiki_page(title, parent, sb_items, deleted_pages, new_widgets, blocks, save=True):
	if save: 
		if not frappe.db.exists("Workspace", title):
			wspace = frappe.new_doc('Workspace')
			wspace.label = title
			wspace.insert()

		doc = frappe.new_doc('Internal Wiki Page')
		doc.title = title
		doc.parent_page = parent
		doc.content = blocks
		doc.insert()
	else:
		doc = frappe.get_doc('Internal Wiki Page', title)
		doc.content = blocks
		doc.save()

	if json.loads(sb_items):
		for seq, d in enumerate(json.loads(sb_items)):
			doc = frappe.get_doc('Internal Wiki Page', d.get('name'))
			doc.sequence_id = seq + 1
			doc.parent_page = d.get('parent_page') or ""
			doc.save()
		doc.title = title
	
	if json.loads(deleted_pages):
		for d in json.loads(deleted_pages):
			wiki_doc = frappe.get_doc('Internal Wiki Page', d)
			wiki_doc.delete()
			wspace_doc = frappe.get_doc('Workspace', d)
			if not wspace_doc.is_standard:
				wspace_doc.delete()
		return 'Build'

	if json.loads(new_widgets):
		save_new_widget(title, new_widgets)

	return doc.title

@frappe.whitelist()
def get_page_content(page):
	return frappe.db.get_value("Internal Wiki Page", page, "content")

@frappe.whitelist()
def get_pages():
	return frappe.db.get_list('Internal Wiki Page', fields=['name', 'icon', 'private', 'parent_page', 'sequence_id'], 
		order_by="sequence_id asc")