# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def get_monthly_results(goal_doctype, goal_field, filter_str, aggregation = 'sum'):
	'''Get monthly aggregation values for given field of doctype'''

	where_clause = ('where ' + filter_str) if filter_str else ''
	results = frappe.db.sql('''
		select
			{0}({1}) as {1}, date_format(creation, '%m-%Y') as month_year
		from
			`{2}`
		{3}
		group by
			month_year'''.format(aggregation, goal_field, "tab" +
			goal_doctype, where_clause), as_dict=True)

	month_to_value_dict = {}
	for d in results:
		month_to_value_dict[d['month_year']] = d[goal_field]

	return month_to_value_dict

@frappe.whitelist()
def get_monthly_goal_graph_data(title, doctype, docname, goal_value_field, goal_total_field,
	goal_doctype, goal_field, filter_str, aggregation="sum"):
	'''
		Get month-wise graph data for a doctype based on aggregation values of a field in the goal doctype

		:param title: Graph title
		:param doctype: doctype of graph doc
		:param docname: of the doc to set the graph in
		:param goal_value_field: goal field of doctype
		:param goal_total_field: current month value field of doctype
		:param goal_doctype: doctype the goal is based on
		:param goal_field: field from which the goal is calculated
		:param filter_str: where clause condition
		:param aggregation: a value like 'count', 'sum', 'avg'

		:return: dict of graph data
	'''

	month_to_value_dict = get_monthly_results(goal_doctype, goal_field, filter_str, aggregation)

	from frappe.utils import today, getdate, formatdate, add_months
	months = []
	values = []
	for i in xrange(0, 12):
		month_value = formatdate(add_months(today(), -i), "MM-yyyy")
		month_word = getdate(month_value).strftime('%b')
		months.insert(0, month_word)
		if month_value in month_to_value_dict:
			values.insert(0, month_to_value_dict[month_value])
		else:
			values.insert(0, 0)

	current_month_year = formatdate(today(), "MM-yyyy")
	current_month_value = 0
	if current_month_year in month_to_value_dict:
		current_month_value = month_to_value_dict[current_month_year]


	# Set doc completed goal value
	frappe.db.set_value(doctype, docname, goal_total_field, current_month_value)

	goal = frappe.get_value(doctype, docname, goal_value_field)

	from frappe.utils.formatters import format_value
	meta = frappe.get_meta(doctype)
	doc = frappe.get_doc(doctype, docname)
	formatted_value = format_value(current_month_value, meta.get_field(goal_total_field), doc)
	formatted_goal = format_value(goal, meta.get_field(goal_value_field), doc)

	data = {
		'title': title,
		# 'subtitle':
		'y_values': values,
		'x_points': months,
		'specific_values': [
			{
				'name': "Goal",
				'line_type': "dashed",
				'value': goal
			},
		],
		'summary_values': [
			{
				'name': "This month",
				'color': 'green',
				'value': formatted_value
			},
			{
				'name': "Goal",
				'color': 'blue',
				'value': formatted_goal
			},
			{
				'name': "Completed",
				'color': 'green',
				'value': str(int(round(current_month_value/float(goal)*100))) + "%"
			}
		]
	}

	return data