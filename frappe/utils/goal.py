# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from contextlib import suppress

import frappe
from frappe import _
from frappe.query_builder.functions import DateFormat, Function
from frappe.query_builder.utils import DocType
from frappe.utils.data import add_to_date, cstr, flt, now_datetime
from frappe.utils.formatters import format_value


def get_monthly_results(
	goal_doctype: str,
	goal_field: str,
	date_col: str,
	filters: dict,
	aggregation: str = "sum",
) -> dict:
    """Get monthly aggregation values for given field of doctype"""

    Table = DocType(goal_doctype)
    date_format = "%m-%Y" if frappe.db.db_type != "postgres" else "MM-YYYY"

    return dict(
    	frappe.qb.get_query(
    		table=goal_doctype,
    		fields=[
    			DateFormat(Table[date_col], date_format).as_("month_year"),
    			Function(aggregation, goal_field),
    		],
    		filters=filters,
    		validate_filters=True,
    	)
    	.groupby("month_year")
    	.run()
    )


@frappe.whitelist()
def get_monthly_goal_graph_data(
	title: str,
	doctype: str,
	docname: str,
	goal_value_field: str,
	goal_total_field: str,
	goal_history_field: str,
	goal_doctype: str,
	goal_doctype_link: str,
	goal_field: str,
	date_field: str,
	aggregation: str = "sum",
	filters: str | dict | None = None,
) -> dict:
    """
    Get month-wise graph data for a doctype based on aggregation values of a field
    in the goal doctype

    Args:
        title (str): Graph title doctype (str): Doctype of graph doc docname
        (str): Docname of the doc to set the graph in goal_value_field (str):
        Goal field of doctype goal_total_field (str): Current month value
        field of doctype goal_history_field (str): Cached history field
        goal_doctype (str): Doctype the goal is based on goal_doctype_link
        (str): Doctype link field in goal_doctype goal_field (str): Field from
        which the goal is calculated date_field (str): Date field aggregation
        (str, optional): Aggregation value like 'count', 'sum', 'avg'.
        Defaults to 'sum'.
        filters (str | dict | None, optional): Optional filters. Defaults to None.

    Returns:
        dict: Dictionary of graph data
    """
    doc = frappe.get_doc(doctype, docname)
    doc.check_permission()

    meta = doc.meta
    goal = doc.get(goal_value_field)
    today_date = now_datetime().date()

    current_month_value = doc.get(goal_total_field)
    current_month_year = today_date.strftime("%m-%Y")  # eg: "02-2022"
    formatted_value = format_value(current_month_value, meta.get_field(goal_total_field), doc)
    history = doc.get(goal_history_field)

    month_to_value_dict = None
    if history and "{" in cstr(history):
        with suppress(ValueError):
            month_to_value_dict = frappe.parse_json(history)

    if month_to_value_dict is None:  # nosemgrep
        doc_filter = {}
        with suppress(ValueError):
            doc_filter = frappe.parse_json(filters or "{}")
        if doctype != goal_doctype:
            doc_filter[goal_doctype_link] = docname

        month_to_value_dict = get_monthly_results(
        	goal_doctype, goal_field, date_field, doc_filter, aggregation
        )

    month_to_value_dict[current_month_year] = current_month_value

    month_labels = []
    dataset_values = []
    values_formatted = []
    y_markers = {}

    summary_values = [
    	{"title": _("This month"), "color": "#ffa00a", "value": formatted_value},
    ]

    if flt(goal) > 0:
        formatted_goal = format_value(goal, meta.get_field(goal_value_field), doc)
        summary_values += [
        	{"title": _("Goal"), "color": "#5e64ff", "value": formatted_goal},
        	{
        		"title": _("Completed"),
        		"color": "#28a745",
        		"value": f"{int(round(flt(current_month_value) / flt(goal) * 100))}%",
        	},
        ]
        y_markers = {"yMarkers": [{"label": _("Goal"), "lineType": "dashed", "value": flt(goal)}]}

    for i in range(12):
        date_value = add_to_date(today_date, months=-i, as_datetime=True)
        month_word = date_value.strftime("%b %y")  # eg: "Feb 22"
        month_labels.insert(0, month_word)

        month_value = date_value.strftime("%m-%Y")  # eg: "02-2022"
        val = month_to_value_dict.get(month_value, 0)
        dataset_values.insert(0, val)
        values_formatted.insert(0, format_value(val, meta.get_field(goal_total_field), doc))

    return {
    	"title": title,
    	"data": {
    		"datasets": [{"values": dataset_values, "formatted": values_formatted}],
    		"labels": month_labels,
    		**y_markers,
    	},
    	"summary": summary_values,
    }
