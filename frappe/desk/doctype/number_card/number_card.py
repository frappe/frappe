# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cint
from frappe.model.naming import append_number_if_name_exists
from frappe.modules.export_file import export_to_files

class NumberCard(Document):
	def autoname(self):
		if not self.name:
			self.name = self.label

		if frappe.db.exists("Number Card", self.name):
			self.name = append_number_if_name_exists('Number Card', self.name)

	def on_update(self):
		if frappe.conf.developer_mode and self.is_standard:
			export_to_files(record_list=[['Number Card', self.name]], record_module=self.module)

def get_permission_query_conditions(user=None):
	if not user:
		user = frappe.session.user

	if user == 'Administrator':
		return

	roles = frappe.get_roles(user)
	if "System Manager" in roles:
		return None

	doctype_condition = False

	allowed_doctypes = [frappe.db.escape(doctype) for doctype in frappe.permissions.get_doctypes_with_read()]

	if allowed_doctypes:
		doctype_condition = '`tabNumber Card`.`document_type` in ({allowed_doctypes})'.format(
			allowed_doctypes=','.join(allowed_doctypes))

	return '''
			{doctype_condition}
		'''.format(doctype_condition=doctype_condition)

def has_permission(doc, ptype, user):
	roles = frappe.get_roles(user)
	if "System Manager" in roles:
		return True

	allowed_doctypes = tuple(frappe.permissions.get_doctypes_with_read())
	if doc.document_type in allowed_doctypes:
		return True

	return False

@frappe.whitelist()
def get_result(doc, filters, to_date=None):
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

	filters = frappe.parse_json(filters)

	if not filters:
			filters = []

	if to_date:
		filters.append([doc.document_type, 'creation', '<', to_date])

	res = frappe.db.get_list(doc.document_type, fields=fields, filters=filters)
	number = res[0]['result'] if res else 0

	return cint(number)

@frappe.whitelist()
def get_percentage_difference(doc, filters, result):
	doc = frappe.parse_json(doc)
	result = frappe.parse_json(result)

	doc = frappe.get_doc('Number Card', doc.name)

	if not doc.get('show_percentage_stats'):
		return

	previous_result = calculate_previous_result(doc, filters)
	difference = (result - previous_result)/100.0

	return difference


def calculate_previous_result(doc, filters):
	from frappe.utils import add_to_date

	current_date = frappe.utils.now()
	if doc.stats_time_interval == 'Daily':
		previous_date = add_to_date(current_date, days=-1)
	elif doc.stats_time_interval == 'Weekly':
		previous_date = add_to_date(current_date, weeks=-1)
	elif doc.stats_time_interval == 'Monthly':
		previous_date = add_to_date(current_date, months=-1)
	else:
		previous_date = add_to_date(current_date, years=-1)

	number = get_result(doc, filters, previous_date)
	return number

@frappe.whitelist()
def create_number_card(args):
	args = frappe.parse_json(args)
	doc = frappe.new_doc('Number Card')

	doc.update(args)
	doc.insert(ignore_permissions=True)
	return doc

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_cards_for_user(doctype, txt, searchfield, start, page_len, filters):
	meta = frappe.get_meta(doctype)
	searchfields = meta.get_search_fields()
	search_conditions = []

	if not frappe.db.exists('DocType', doctype):
		return

	if txt:
		for field in searchfields:
			search_conditions.append('`tab{doctype}`.`{field}` like %(txt)s'.format(field=field, doctype=doctype, txt=txt))

		search_conditions = ' or '.join(search_conditions)

	search_conditions = 'and (' + search_conditions +')' if search_conditions else ''
	conditions, values = frappe.db.build_conditions(filters)
	values['txt'] = '%' + txt + '%'

	return frappe.db.sql(
		'''select
			`tabNumber Card`.name, `tabNumber Card`.label, `tabNumber Card`.document_type
		from
			`tabNumber Card`
		where
			{conditions} and
			(`tabNumber Card`.owner = '{user}' or
			`tabNumber Card`.is_public = 1)
			{search_conditions}
	'''.format(
		filters=filters,
		user=frappe.session.user,
		search_conditions=search_conditions,
		conditions=conditions
	), values)

@frappe.whitelist()
def create_report_number_card(args):
	card = create_number_card(args)
	args = frappe.parse_json(args)
	args.name = card.name
	if args.dashboard:
		add_card_to_dashboard(frappe.as_json(args))

@frappe.whitelist()
def add_card_to_dashboard(args):
	args = frappe.parse_json(args)

	dashboard = frappe.get_doc('Dashboard', args.dashboard)
	dashboard_link = frappe.new_doc('Number Card Link')
	dashboard_link.card = args.name

	if args.set_standard and dashboard.is_standard:
		card = frappe.get_doc('Number Card', dashboard_link.card)
		card.is_standard = 1
		card.module = dashboard.module
		card.save()

	dashboard.append('cards', dashboard_link)
	dashboard.save()