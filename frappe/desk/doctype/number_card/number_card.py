# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists

class NumberCard(Document):
	pass


@frappe.whitelist()
def get_result(doc):
	doc = frappe.parse_json(doc)
	fields = []
	sql_function_map = {
		'Count': 'count',
		'Sum': 'sum',
		'Average': 'avg',
		'Minimum': 'min',
		'Maximum': 'max'
	}

	function = sql_function_map[doc.function]

	if function == 'count':
		fields = ['{function}(*) as result'.format(function=function)]
	else:
		fields = ['{function}({based_on}) as result'.format(function=function, based_on=doc.aggregate_function_based_on)]

	filters = frappe.parse_json(doc.filters_json)
	number = frappe.db.get_all(doc.document_type, fields = fields, filters = filters)[0]['result']
	number = round(number, 2) if isinstance(number, float) else number

	return number

@frappe.whitelist()
def create_number_card(args):
	args = frappe.parse_json(args)
	doc = frappe.new_doc('Number Card')
	roles = frappe.get_roles(frappe.session.user)
	if 'Sytem Manager' in roles or 'Dashboard Manager' in roles:
		doc.is_standard = 1
	doc.update(args)
	doc.insert(ignore_permissions=True)
	return doc

def get_cards_for_user(doctype, txt, searchfield, start, page_len, filters):
	or_filters = {'owner': frappe.session.user, 'is_standard': 1}
	return frappe.db.get_list('Number Card',
		fields=['name', 'label'],
		filters=filters,
		or_filters=or_filters,
		as_list = 1)