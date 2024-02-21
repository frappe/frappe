# Copyright (c) 2013, Frappe Technologies and contributors
# License: MIT. See LICENSE

from datetime import datetime

import frappe
from frappe.query_builder.functions import Coalesce, Count
from frappe.utils import getdate
from frappe.utils.dateutils import get_dates_from_timegrain


def execute(filters=None):
	return WebsiteAnalytics(filters).run()


class WebsiteAnalytics:
	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})

		if not self.filters.to_date:
			self.filters.to_date = datetime.now()

		if not self.filters.from_date:
			self.filters.from_date = frappe.utils.add_days(self.filters.to_date, -7)

		if not self.filters.range:
			self.filters.range = "Daily"

		self.filters.to_date = frappe.utils.add_days(self.filters.to_date, 1)
		self.query_filters = {"creation": ["between", [self.filters.from_date, self.filters.to_date]]}
		self.group_by = self.filters.group_by

	def run(self):
		columns = self.get_columns()
		data = self.get_data()
		chart = self.get_chart_data()
		summary = self.get_report_summary()

		return columns, data[:250], None, chart, summary

	def get_columns(self):
		meta = frappe.get_meta("Web Page View")
		group_by = meta.get_field(self.group_by)
		return [
			{
				"fieldname": group_by.fieldname,
				"label": group_by.label,
				"fieldtype": "Data",
				"width": 500,
				"align": "left",
			},
			{"fieldname": "count", "label": "Page Views", "fieldtype": "Int", "width": 150},
			{"fieldname": "unique_count", "label": "Unique Visitors", "fieldtype": "Int", "width": 150},
		]

	def get_data(self):
		WebPageView = frappe.qb.DocType("Web Page View")
		count_all = Count("*").as_("count")
		case = frappe.qb.terms.Case().when(WebPageView.is_unique == "1", "1")
		count_is_unique = Count(case).as_("unique_count")

		return (
			frappe.qb.from_(WebPageView)
			.select(self.group_by, count_all, count_is_unique)
			.where(
				Coalesce(WebPageView.creation, "0001-01-01")[self.filters.from_date : self.filters.to_date]
			)
			.groupby(self.group_by)
			.orderby("count", order=frappe.qb.desc)
		).run()

	def _get_query_for_mariadb(self):
		filters_range = self.filters.range
		field = "creation"
		date_format = "%Y-%m-%d"

		if filters_range == "Weekly":
			field = "ADDDATE(creation, INTERVAL 1-DAYOFWEEK(creation) DAY)"

		elif filters_range == "Monthly":
			date_format = "%Y-%m-01"

		query = f"""
				SELECT
					DATE_FORMAT({field}, %s) as date,
					COUNT(*) as count,
					COUNT(CASE WHEN is_unique = 1 THEN 1 END) as unique_count
				FROM `tabWeb Page View`
				WHERE creation BETWEEN %s AND %s
				GROUP BY DATE_FORMAT({field}, %s)
				ORDER BY creation
			"""

		values = (date_format, self.filters.from_date, self.filters.to_date, date_format)

		return query, values

	def _get_query_for_postgres(self):
		filters_range = self.filters.range
		field = "creation"
		granularity = "day"

		if filters_range == "Weekly":
			granularity = "week"

		elif filters_range == "Monthly":
			granularity = "day"

		query = f"""
				SELECT
					DATE_TRUNC(%s, {field}) as date,
					COUNT(*) as count,
					COUNT(CASE WHEN CAST(is_unique as Integer) = 1 THEN 1 END) as unique_count
				FROM "tabWeb Page View"
				WHERE  coalesce("tabWeb Page View".{field}, '0001-01-01') BETWEEN %s AND %s
				GROUP BY date_trunc(%s, {field})
				ORDER BY date
			"""

		values = (granularity, self.filters.from_date, self.filters.to_date, granularity)

		return query, values

	def get_chart_data(self):
		current_dialect = frappe.db.db_type or "mariadb"

		if current_dialect == "mariadb":
			query, values = self._get_query_for_mariadb()
		else:
			query, values = self._get_query_for_postgres()

		self.chart_data = frappe.db.sql(query, values=values, as_dict=1)

		return self.prepare_chart_data(self.chart_data)

	def prepare_chart_data(self, data):
		date_range = get_dates_from_timegrain(
			self.filters.from_date, self.filters.to_date, self.filters.range
		)
		if self.filters.range == "Monthly":
			date_range = [frappe.utils.add_days(dd, 1) for dd in date_range]

		labels = []
		total_dataset = []
		unique_dataset = []

		def get_data_for_date(date):
			for item in data:
				item_date = getdate(item.get("date"))
				if item_date == date:
					return item
			return {"count": 0, "unique_count": 0}

		for date in date_range:
			labels.append(date.strftime("%b %d %Y"))
			match = get_data_for_date(date)
			total_dataset.append(match.get("count", 0))
			unique_dataset.append(match.get("unique_count", 0))

		chart = {
			"data": {
				"labels": labels,
				"datasets": [
					{"name": "Total Views", "type": "line", "values": total_dataset},
					{"name": "Unique Visits", "type": "line", "values": unique_dataset},
				],
			},
			"type": "axis-mixed",
			"lineOptions": {
				"regionFill": 1,
			},
			"axisOptions": {"xIsSeries": 1},
			"colors": ["#7cd6fd", "#5e64ff"],
		}

		return chart

	def get_report_summary(self):
		total_count = 0
		unique_count = 0
		for data in self.chart_data:
			unique_count += data.get("unique_count")
			total_count += data.get("count")

		return [
			{
				"value": total_count,
				"label": "Total Page Views",
				"datatype": "Int",
			},
			{
				"value": unique_count,
				"label": "Unique Page Views",
				"datatype": "Int",
			},
		]
