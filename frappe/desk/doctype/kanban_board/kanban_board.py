# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe import _
from frappe.model.document import Document

class KanbanBoard(Document):
	pass

@frappe.whitelist()
def add_column(board_name, column_title):
	'''Adds new column to Kanban Board'''
	doc = frappe.get_doc("Kanban Board", board_name)
	for col in doc.columns:
		if column_title == col.column_name:
			frappe.throw(_("Column <b>{0}</b> already exist.").format(column_title))

	doc.append("columns", dict(
		column_name=column_title,
		color=""
	))
	doc.save()
	return doc.columns

@frappe.whitelist()
def archive_restore_column(board_name, column_title, status):
	'''Set column's status to status'''
	doc = frappe.get_doc("Kanban Board", board_name)
	for col in doc.columns:
		if column_title == col.column_name:
			col.status = status

	doc.save()
	return doc.columns

@frappe.whitelist()
def update_doc(doc):
	'''Updates the doc when card is edited'''
	doc = json.loads(doc)

	try:
		to_update = doc
		doctype = doc['doctype']
		docname = doc['name']
		doc = frappe.get_doc(doctype, docname)
		doc.update(to_update)
		doc.save()
	except:
		return {
			'doc': doc,
			'exc': frappe.utils.get_traceback()
		}
	return doc

@frappe.whitelist()
def update_order(board_name, column_title, order):
	'''Save the order of cards in a column'''
	doc = frappe.get_doc('Kanban Board', board_name)

	for col in doc.columns:
		if column_title == col.column_name:
			col.order = order
	doc.save()
	return doc