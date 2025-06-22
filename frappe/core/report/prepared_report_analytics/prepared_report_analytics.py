# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

from pypika import Order

import frappe
from frappe import _, qb
from frappe.query_builder import Criterion
from frappe.utils import add_months, nowdate


def execute(filters: dict | None = None):
	"""Return columns and data for the report.

	This is the main entry point for the report. It accepts the filters as a
	dictionary and should return columns and data. It is called by the framework
	every time the report is refreshed or a filter is updated.
	"""
	columns = get_columns(filters)
	data = get_data(filters=filters)

	return columns, data


def get_columns(filters) -> list[dict]:
	"""Return columns for the report.

	One field definition per column, just like a DocType field definition.
	"""
	return [
		{
			"label": _("Prepared Report"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Prepared Report",
			"width": 250,
		},
		{
			"label": _("Report Name"),
			"fieldname": "report_name",
			"fieldtype": "Data",
			"width": 250,
		},
		{
			"label": _("Start"),
			"fieldname": "creation",
			"fieldtype": "DateTime",
			"width": 250,
		},
		{
			"label": _("End"),
			"fieldname": "report_end_time",
			"fieldtype": "DateTime",
			"width": 250,
		},
		{
			"label": _("Runtime in Minutes") if filters.in_minutes else _("Runtime in Seconds"),
			"fieldname": "runtime",
			"fieldtype": "float",
			"width": 250,
		},
		{
			"label": _("Memory Usage in MB"),
			"fieldname": "peak_memory_usage",
			"fieldtype": "float",
			"width": 250,
		},
	]


def get_data(filters) -> list[list]:
	"""Return data for the report.

	The report data is a list of rows, with each row being a list of cell values.
	"""

	pr = qb.DocType("Prepared Report")

	conditions = [pr.status.eq("Completed"), pr.creation.gte(add_months(nowdate(), -2))]

	if filters.report:
		conditions.append(pr.report_name.like(f"%{filters.report}%"))

	divisor = 1
	if filters.in_minutes:
		divisor = 60

	query = (
		qb.from_(pr)
		.select(
			pr.name,
			pr.report_name,
			pr.creation,
			pr.report_end_time,
			(pr.peak_memory_usage / 1024).as_("peak_memory_usage"),
		)
		.select(((pr.report_end_time - pr.creation) / divisor).as_("runtime"))
		.where(Criterion.all(conditions))
		.orderby(qb.Field("runtime"), order=Order.desc)
	)
	if filters.top_10:
		query = query.limit(10)

	res = query.run(as_dict=True)

	return res
