# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class InternalWikiPage(Document):
	pass

def new_internal_wiki_page(title, blocks, parent, parentfield):
	new_doc = frappe.new_doc('Internal Wiki Page')
	new_doc.title = title
	new_doc.content = blocks
	new_doc.parent_page = parent
	new_doc.parentfield = parentfield
	return new_doc

def delete_page(user, wiki_page):
	doc = frappe.get_doc("Internal Wiki", user)
	for idx, page in enumerate(doc.wiki_pages):
		if page.title == wiki_page.get("title") and page.parent == wiki_page.get("parent_wiki"):
			del doc.wiki_pages[idx]
	doc.save(ignore_permissions=True)

def sort_page(user, pages):
	doc = frappe.get_doc("Internal Wiki", user)
	for seq, d in enumerate(pages):
		for page in doc.wiki_pages:
			if page.title == d.get('title'):
				page.idx = seq + 1
				page.parent_page = d.get('parent_page') or ""
				break
	doc.save(ignore_permissions=True)