# Copyright (c) 2013, Frappe Technologies and contributors
# License: MIT. See LICENSE

from datetime import datetime

import frappe
from frappe.query_builder.functions import Coalesce, Count, Function
from frappe.utils import get_start_of_week_index, getdate
from frappe.utils.dateutils import get_dates_from_timegrain
from frappe.utils.logging import get_log_db, log_table


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
		qb, table = log_table("Web Page View")
		count_all = Count("*").as_("count")
		case = qb.terms.Case().when(table.is_unique == "1", "1")
		count_is_unique = Count(case).as_("unique_count")

		return get_log_db().sql(
			qb.from_(table)
			.select(self.group_by, count_all, count_is_unique)
			.where(Coalesce(table.creation, "0001-01-01")[self.filters.from_date : self.filters.to_date])
			.groupby(self.group_by)
			.orderby("count", order=qb.desc)
		)

	def _creation_bucket(self, table):
		"""Return the expression that buckets `creation` into one point on the chart.

		Written as SQLite date functions because Web Page View keeps its rows in the site's log
		database, which is always SQLite -- the earlier MariaDB and Postgres variants of this
		query have nothing left to run against.

		Each bucket is the value `prepare_chart_data` looks up, so it has to be the same day
		`get_dates_from_timegrain` puts on the x-axis: the day itself, the *last* day of the
		week, the first of the month. `date(creation, 'weekday N')` moves forward to the next
		weekday N, staying put if `creation` already is one, so naming the day the week ends on
		lands exactly on that week's label. `Weekday` numbers days the way SQLite does -- Sunday
		is 0 -- so the setting can be passed straight through, and a site that starts its week
		on a Monday buckets to Sundays like its labels do.

		The week grain used to be `ADDDATE(creation, INTERVAL 1-DAYOFWEEK(creation) DAY)`, the
		week *start*, hardcoded to Sunday. It never matched a label, so every Weekly chart read
		as a flat zero line.
		"""
		if self.filters.range == "Weekly":
			end_of_week = (get_start_of_week_index() + 6) % 7
			return Function("DATE", table.creation, f"weekday {end_of_week}")

		if self.filters.range == "Monthly":
			return Function("STRFTIME", "%Y-%m-01", table.creation)

		return Function("DATE", table.creation)

	def get_chart_data(self):
		qb, table = log_table("Web Page View")
		bucket = self._creation_bucket(table)
		case = qb.terms.Case().when(table.is_unique == "1", "1")

		# `as_` copies the term rather than renaming it in place, so grouping and ordering
		# still happen on the expression itself and not on its alias.
		self.chart_data = get_log_db().sql(
			qb.from_(table)
			.select(
				bucket.as_("date"),
				Count("*").as_("count"),
				Count(case).as_("unique_count"),
			)
			.where(table.creation[self.filters.from_date : self.filters.to_date])
			.groupby(bucket)
			.orderby(bucket),
			as_dict=True,
		)

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
