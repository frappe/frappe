# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from six.moves import xrange

def get_monthly_results(goal_doctype, goal_field, date_col, filter_str, aggregation = 'sum'):
	'''Get monthly aggregation values for given field of doctype'''

	where_clause = ('where ' + filter_str) if filter_str else ''
	results = frappe.db.sql('''
		select
			{0}({1}) as {1}, date_format({2}, '%m-%Y') as month_year
		from
			`{3}`
		{4}
		group by
			month_year'''.format(aggregation, goal_field, date_col, "tab" +
			goal_doctype, where_clause), as_dict=True)

	month_to_value_dict = {}
	for d in results:
		month_to_value_dict[d['month_year']] = d[goal_field]

	return month_to_value_dict

@frappe.whitelist()
def get_monthly_goal_graph_data(title, doctype, docname, goal_value_field, goal_total_field, goal_history_field,
	goal_doctype, goal_doctype_link, goal_field, date_field, filter_str, aggregation="sum"):
	'''
		Get month-wise graph data for a doctype based on aggregation values of a field in the goal doctype

		:param title: Graph title
		:param doctype: doctype of graph doc
		:param docname: of the doc to set the graph in
		:param goal_value_field: goal field of doctype
		:param goal_total_field: current month value field of doctype
		:param goal_history_field: cached history field
		:param goal_doctype: doctype the goal is based on
		:param goal_doctype_link: doctype link field in goal_doctype
		:param goal_field: field from which the goal is calculated
		:param filter_str: where clause condition
		:param aggregation: a value like 'count', 'sum', 'avg'

		:return: dict of graph data
	'''

	from frappe.utils.formatters import format_value
	import json

	meta = frappe.get_meta(doctype)
	doc = frappe.get_doc(doctype, docname)

	goal = doc.get(goal_value_field)
	formatted_goal = format_value(goal, meta.get_field(goal_value_field), doc)

	current_month_value = doc.get(goal_total_field)
	formatted_value = format_value(current_month_value, meta.get_field(goal_total_field), doc)

	from frappe.utils import today, getdate, formatdate, add_months
	current_month_year = formatdate(today(), "MM-yyyy")

	history = doc.get(goal_history_field)
	try:
		month_to_value_dict = json.loads(history) if history and '{' in history else None
	except ValueError:
		month_to_value_dict = None

	if month_to_value_dict is None:
		doc_filter = (goal_doctype_link + ' = "' + docname + '"') if doctype != goal_doctype else ''
		if filter_str:
			doc_filter += ' and ' + filter_str if doc_filter else filter_str
		month_to_value_dict = get_monthly_results(goal_doctype, goal_field, date_field, doc_filter, aggregation)
		frappe.db.set_value(doctype, docname, goal_history_field, json.dumps(month_to_value_dict))

	month_to_value_dict[current_month_year] = current_month_value

	months = []
	months_formatted = []
	values = []
	values_formatted = []
	for i in xrange(0, 12):
		month_value = formatdate(add_months(today(), -i), "MM-yyyy")
		month_word = getdate(month_value).strftime('%b')
		month_year = getdate(month_value).strftime('%B') + ', ' + getdate(month_value).strftime('%Y')
		months.insert(0, month_word)
		months_formatted.insert(0, month_year)
		if month_value in month_to_value_dict:
			val = month_to_value_dict[month_value]
		else:
			val = 0
		values.insert(0, val)
		values_formatted.insert(0, format_value(val, meta.get_field(goal_total_field), doc))

	specific_values = []
	summary_values = [
		{
			'name': _("This month"),
			'color': 'green',
			'value': formatted_value
		}
	]

	if float(goal) > 0:
		specific_values = [
			{
				'name': _("Goal"),
				'line_type': "dashed",
				'value': goal
			},
		]
		summary_values += [
			{
				'name': _("Goal"),
				'color': 'blue',
				'value': formatted_goal
			},
			{
				'name': _("Completed"),
				'color': 'green',
				'value': str(int(round(float(current_month_value)/float(goal)*100))) + "%"
			}
		]

	data = {
		'title': title,
		# 'subtitle':
		'y': [
			{
				'color': 'green',
				'values': values,
				'formatted': values_formatted
			}
		],
		'x': {
			'values': months,
			'formatted': months_formatted
		},

		'specific_values': specific_values,
		'summary': summary_values
	}

	return data
