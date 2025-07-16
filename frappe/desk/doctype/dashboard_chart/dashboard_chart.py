# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import datetime
import json

import frappe
from frappe import _
from frappe.boot import get_allowed_report_names
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.modules.export_file import export_to_files
from frappe.utils import cint, flt, get_datetime, getdate, has_common, now_datetime, nowdate
from frappe.utils.dashboard import cache_source
from frappe.utils.data import format_date
from frappe.utils.dateutils import (
	get_dates_from_timegrain,
	get_from_date_from_timespan,
	get_period,
	get_period_beginning,
)
from frappe.utils.modules import get_modules_from_all_apps_for_user


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return

	roles = frappe.get_roles(user)
	if "System Manager" in roles:
		return None

	doctype_condition = False
	report_condition = False
	module_condition = False

	allowed_doctypes = [frappe.db.escape(doctype) for doctype in frappe.permissions.get_doctypes_with_read()]
	allowed_reports = [frappe.db.escape(report) for report in get_allowed_report_names()]
	allowed_modules = [
		frappe.db.escape(module.get("module_name")) for module in get_modules_from_all_apps_for_user()
	]

	if allowed_doctypes:
		doctype_condition = "`tabDashboard Chart`.`document_type` in ({allowed_doctypes})".format(
			allowed_doctypes=",".join(allowed_doctypes)
		)
	if allowed_reports:
		report_condition = "`tabDashboard Chart`.`report_name` in ({allowed_reports})".format(
			allowed_reports=",".join(allowed_reports)
		)
	if allowed_modules:
		module_condition = """`tabDashboard Chart`.`module` in ({allowed_modules})
			or `tabDashboard Chart`.`module` is NULL""".format(allowed_modules=",".join(allowed_modules))

	return f"""
		((`tabDashboard Chart`.`chart_type` in ('Count', 'Sum', 'Average')
		and {doctype_condition})
		or
		(`tabDashboard Chart`.`chart_type` = 'Report'
		and {report_condition}))
		and
		({module_condition})
	"""


def has_permission(doc, ptype, user):
	roles = frappe.get_roles(user)
	if "System Manager" in roles:
		return True

	if doc.roles:
		allowed = [d.role for d in doc.roles]
		if has_common(roles, allowed):
			return True
	elif doc.chart_type == "Report":
		if doc.report_name in get_allowed_report_names():
			return True
	else:
		allowed_doctypes = frappe.permissions.get_doctypes_with_read()
		if doc.document_type in allowed_doctypes:
			return True

	return False


@frappe.whitelist()
@cache_source
def get(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
	refresh=None,
):
	if chart_name:
		chart: DashboardChart = frappe.get_doc("Dashboard Chart", chart_name)
	else:
		chart = frappe._dict(frappe.parse_json(chart))

	heatmap_year = heatmap_year or chart.heatmap_year
	timespan = timespan or chart.timespan

	if timespan == "Select Date Range":
		if from_date and len(from_date):
			from_date = get_datetime(from_date)
		else:
			from_date = chart.from_date

		if to_date and len(to_date):
			to_date = get_datetime(to_date)
		else:
			to_date = get_datetime(chart.to_date)

	timegrain = time_interval or chart.time_interval
	filters = frappe.parse_json(filters) or frappe.parse_json(chart.filters_json)
	if not filters:
		filters = []

	# don't include cancelled documents
	filters.append([chart.document_type, "docstatus", "<", 2])

	if chart.chart_type == "Group By":
		chart_config = get_group_by_chart_config(chart, filters)
	else:
		if chart.type == "Heatmap":
			chart_config = get_heatmap_chart_config(chart, filters, heatmap_year)
		else:
			chart_config = get_chart_config(chart, filters, timespan, timegrain, from_date, to_date)

	return chart_config


@frappe.whitelist()
def create_dashboard_chart(args):
	args = frappe.parse_json(args)
	doc = frappe.new_doc("Dashboard Chart")

	doc.update(args)

	if args.get("custom_options"):
		doc.custom_options = json.dumps(args.get("custom_options"))

	if frappe.db.exists("Dashboard Chart", args.chart_name):
		args.chart_name = append_number_if_name_exists("Dashboard Chart", args.chart_name)
		doc.chart_name = args.chart_name
	doc.insert(ignore_permissions=True)
	return doc


@frappe.whitelist()
def create_report_chart(args):
	doc = create_dashboard_chart(args)
	args = frappe.parse_json(args)
	args.chart_name = doc.chart_name
	if args.dashboard:
		add_chart_to_dashboard(json.dumps(args))


@frappe.whitelist()
def add_chart_to_dashboard(args):
	args = frappe.parse_json(args)

	dashboard = frappe.get_doc("Dashboard", args.dashboard)
	dashboard_link = frappe.new_doc("Dashboard Chart Link")
	dashboard_link.chart = args.chart_name or args.name

	if args.set_standard and dashboard.is_standard:
		chart = frappe.get_doc("Dashboard Chart", dashboard_link.chart)
		chart.is_standard = 1
		chart.module = dashboard.module
		chart.save()

	dashboard.append("charts", dashboard_link)
	dashboard.save()
	frappe.db.commit()


def get_chart_config(chart, filters, timespan, timegrain, from_date, to_date):
	if not from_date:
		from_date = get_from_date_from_timespan(to_date, timespan)
		from_date = get_period_beginning(from_date, timegrain)
	if not to_date:
		to_date = now_datetime()

	doctype = chart.document_type
	datefield = chart.based_on
	value_field = chart.value_based_on or "1"
	from_date = from_date.strftime("%Y-%m-%d")
	to_date = to_date

	filters.append([doctype, datefield, ">=", from_date])
	filters.append([doctype, datefield, "<=", to_date])

	data = frappe.get_list(
		doctype,
		fields=[datefield, f"SUM({value_field})", "COUNT(*)"],
		filters=filters,
		group_by=datefield,
		order_by=datefield,
		as_list=True,
		parent_doctype=chart.parent_document_type,
	)

	result = get_result(data, timegrain, from_date, to_date, chart.chart_type)

	return {
		"labels": [
			format_date(get_period(r[0], timegrain), parse_day_first=True)
			if timegrain in ("Daily", "Weekly")
			else get_period(r[0], timegrain)
			for r in result
		],
		"datasets": [{"name": chart.name, "values": [r[1] for r in result]}],
	}


def get_heatmap_chart_config(chart, filters, heatmap_year):
	aggregate_function = get_aggregate_function(chart.chart_type)
	value_field = chart.value_based_on or "1"
	doctype = chart.document_type
	datefield = chart.based_on
	year = cint(heatmap_year) if heatmap_year else getdate(nowdate()).year
	year_start_date = datetime.date(year, 1, 1).strftime("%Y-%m-%d")
	next_year_start_date = datetime.date(year + 1, 1, 1).strftime("%Y-%m-%d")

	filters.append([doctype, datefield, ">", f"{year_start_date}"])
	filters.append([doctype, datefield, "<", f"{next_year_start_date}"])

	if frappe.db.db_type == "mariadb":
		timestamp_field = f"unix_timestamp({datefield})"
	else:
		timestamp_field = f"extract(epoch from timestamp {datefield})"

	data = dict(
		frappe.get_all(
			doctype,
			fields=[
				timestamp_field,
				f"{aggregate_function}({value_field})",
			],
			filters=filters,
			group_by=f"date({datefield})",
			as_list=1,
			order_by=f"{datefield} asc",
			ignore_ifnull=True,
		)
	)

	return {
		"labels": [],
		"dataPoints": data,
	}


def get_group_by_chart_config(chart, filters) -> dict | None:
	aggregate_function = get_aggregate_function(chart.group_by_type)
	value_field = chart.aggregate_function_based_on or "1"
	group_by_field = chart.group_by_based_on
	doctype = chart.document_type

	data = frappe.get_list(
		doctype,
		fields=[
			f"{group_by_field} as name",
			f"{aggregate_function}({value_field}) as count",
		],
		filters=filters,
		parent_doctype=chart.parent_document_type,
		group_by=group_by_field,
		order_by="count desc",
		ignore_ifnull=True,
	)

	group_by_field_field = frappe.get_meta(doctype).get_field(
		group_by_field
	)  # get info about @group_by_field

	if data and group_by_field_field.fieldtype == "Link":  # if @group_by_field is link
		title_field = frappe.get_meta(group_by_field_field.options)  # get title field
		if title_field.title_field:  # if has title_field
			for item in data:  # replace chart labels from name to title value
				item.name = frappe.get_value(group_by_field_field.options, item.name, title_field.title_field)

	if data:
		return {
			"labels": [item.get("name", "Not Specified") for item in data],
			"datasets": [{"name": chart.name, "values": [item["count"] for item in data]}],
		}
	return None


def get_aggregate_function(chart_type):
	return {
		"Sum": "SUM",
		"Count": "COUNT",
		"Average": "AVG",
	}[chart_type]


def get_result(data, timegrain, from_date, to_date, chart_type):
	dates = get_dates_from_timegrain(from_date, to_date, timegrain)
	result = [[date, 0] for date in dates]
	data_index = 0
	if data:
		for d in result:
			count = 0
			while data_index < len(data) and getdate(data[data_index][0]) <= d[0]:
				d[1] += flt(data[data_index][1])
				count += flt(data[data_index][2])
				data_index += 1
			if chart_type == "Average" and count != 0:
				d[1] = d[1] / count
			if chart_type == "Count":
				d[1] = count

	return result


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_charts_for_user(doctype, txt, searchfield, start, page_len, filters):
	or_filters = {"owner": frappe.session.user, "is_public": 1}
	return frappe.db.get_list(
		"Dashboard Chart", fields=["name"], filters=filters, or_filters=or_filters, as_list=1
	)


class DashboardChart(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.has_role.has_role import HasRole
		from frappe.desk.doctype.dashboard_chart_field.dashboard_chart_field import DashboardChartField
		from frappe.types import DF

		aggregate_function_based_on: DF.Literal[None]
		based_on: DF.Literal[None]
		chart_name: DF.Data
		chart_type: DF.Literal["Count", "Sum", "Average", "Group By", "Custom", "Report"]
		color: DF.Color | None
		currency: DF.Link | None
		custom_options: DF.Code | None
		document_type: DF.Link | None
		dynamic_filters_json: DF.Code | None
		filters_json: DF.Code
		from_date: DF.Date | None
		group_by_based_on: DF.Literal[None]
		group_by_type: DF.Literal["Count", "Sum", "Average"]
		heatmap_year: DF.Literal[None]
		is_public: DF.Check
		is_standard: DF.Check
		last_synced_on: DF.Datetime | None
		module: DF.Link | None
		number_of_groups: DF.Int
		parent_document_type: DF.Link | None
		report_name: DF.Link | None
		roles: DF.Table[HasRole]
		source: DF.Link | None
		time_interval: DF.Literal["Yearly", "Quarterly", "Monthly", "Weekly", "Daily"]
		timeseries: DF.Check
		timespan: DF.Literal["Last Year", "Last Quarter", "Last Month", "Last Week", "Select Date Range"]
		to_date: DF.Date | None
		type: DF.Literal["Line", "Bar", "Percentage", "Pie", "Donut", "Heatmap"]
		use_report_chart: DF.Check
		value_based_on: DF.Literal[None]
		x_field: DF.Literal[None]
		y_axis: DF.Table[DashboardChartField]
	# end: auto-generated types

	def on_update(self):
		frappe.cache.delete_key(f"chart-data:{self.name}")
		if frappe.conf.developer_mode and self.is_standard:
			export_to_files(record_list=[["Dashboard Chart", self.name]], record_module=self.module)

	def validate(self):
		if not frappe.conf.developer_mode and self.is_standard:
			frappe.throw(_("Cannot edit Standard charts"))
		if self.chart_type != "Custom" and self.chart_type != "Report":
			self.check_required_field()
			self.check_document_type()

		self.validate_custom_options()

	def check_required_field(self):
		if not self.document_type:
			frappe.throw(_("Document type is required to create a dashboard chart"))

		if (
			self.document_type
			and frappe.get_meta(self.document_type).istable
			and not self.parent_document_type
		):
			frappe.throw(_("Parent document type is required to create a dashboard chart"))

		if self.chart_type == "Group By":
			if not self.group_by_based_on:
				frappe.throw(_("Group By field is required to create a dashboard chart"))
			if self.group_by_type in ["Sum", "Average"] and not self.aggregate_function_based_on:
				frappe.throw(_("Aggregate Function field is required to create a dashboard chart"))
		else:
			if not self.based_on:
				frappe.throw(_("Time series based on is required to create a dashboard chart"))

	def check_document_type(self):
		if frappe.get_meta(self.document_type).issingle:
			frappe.throw(_("You cannot create a dashboard chart from single DocTypes"))

	def validate_custom_options(self):
		if self.custom_options:
			try:
				json.loads(self.custom_options)
			except ValueError as error:
				frappe.throw(_("Invalid json added in the custom options: {0}").format(error))


@frappe.whitelist()
def get_parent_doctypes(child_type: str) -> list[str]:
	"""Get all parent doctypes that have the child doctype."""
	assert isinstance(child_type, str)

	standard = frappe.get_all(
		"DocField",
		fields="parent",
		filters={"fieldtype": "Table", "options": child_type},
		pluck="parent",
	)

	custom = frappe.get_all(
		"Custom Field",
		fields="dt",
		filters={"fieldtype": "Table", "options": child_type},
		pluck="dt",
	)

	return standard + custom
