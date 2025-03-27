# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import datetime

import frappe
import frappe.defaults
from frappe.locale import get_date_format
from frappe.utils import add_to_date, get_datetime, getdate
from frappe.utils.data import (
	get_first_day,
	get_first_day_of_week,
	get_last_day,
	get_last_day_of_week,
	get_quarter_ending,
	get_quarter_start,
	get_year_ending,
	get_year_start,
)

# global values -- used for caching
dateformats = {
	"yyyy-mm-dd": "%Y-%m-%d",
	"mm/dd/yyyy": "%m/%d/%Y",
	"mm-dd-yyyy": "%m-%d-%Y",
	"mm/dd/yy": "%m/%d/%y",
	"dd-mmm-yyyy": "%d-%b-%Y",  # numbers app format
	"dd/mm/yyyy": "%d/%m/%Y",
	"dd.mm.yyyy": "%d.%m.%Y",
	"dd.mm.yy": "%d.%m.%y",
	"dd-mm-yyyy": "%d-%m-%Y",
	"dd/mm/yy": "%d/%m/%y",
}


def user_to_str(date, date_format=None):
	if not date:
		return date

	if not date_format:
		date_format = get_user_date_format()

	try:
		return datetime.datetime.strptime(date, dateformats[date_format]).strftime("%Y-%m-%d")
	except ValueError:
		raise ValueError(f"Date {date} must be in format {date_format}")


def parse_date(date):
	"""tries to parse given date to system's format i.e. yyyy-mm-dd. returns a string"""
	parsed_date = None

	if " " in date:
		# as date-timestamp, remove the time part
		date = date.split(" ", 1)[0]

	# why the sorting? checking should be done in a predictable order
	check_formats = [None, *sorted(list(dateformats), reverse=not get_user_date_format().startswith("dd"))]

	for f in check_formats:
		try:
			parsed_date = user_to_str(date, f)
			if parsed_date:
				break
		except ValueError:
			pass

	if not parsed_date:
		raise Exception(
			f"""Cannot understand date - '{date}'.
			Try formatting it like your default format - '{get_user_date_format()}'"""
		)

	return parsed_date


def get_user_date_format():
	if getattr(frappe.local, "user_date_format", None) is None:
		frappe.local.user_date_format = get_date_format()

	return frappe.local.user_date_format


def datetime_in_user_format(date_time):
	if not date_time:
		return ""
	if isinstance(date_time, str):
		date_time = get_datetime(date_time)
	from frappe.utils import formatdate

	return formatdate(date_time.date()) + " " + date_time.strftime("%H:%M")


def get_dates_from_timegrain(from_date, to_date, timegrain="Daily"):
	from_date = getdate(from_date)
	to_date = getdate(to_date)

	days = months = years = 0
	if "Daily" == timegrain:
		days = 1
	elif "Weekly" == timegrain:
		days = 7
	elif "Monthly" == timegrain:
		months = 1
	elif "Quarterly" == timegrain:
		months = 3
	elif "Yearly" == timegrain:
		months = 1

	dates = [get_period_ending(from_date, timegrain)]

	while getdate(dates[-1]) < getdate(to_date):
		if "Weekly" == timegrain:
			date = get_last_day_of_week(add_to_date(dates[-1], years=years, months=months, days=days))
		else:
			date = get_period_ending(add_to_date(dates[-1], years=years, months=months, days=days), timegrain)
		dates.append(date)
	return dates


def get_from_date_from_timespan(to_date, timespan):
	days = months = years = 0
	if timespan == "Last Week":
		days = -7
	if timespan == "Last Month":
		months = -1
	elif timespan == "Last Quarter":
		months = -3
	elif timespan == "Last Year":
		years = -1
	elif timespan == "All Time":
		years = -50
	return add_to_date(to_date, years=years, months=months, days=days, as_datetime=True)


def get_period(date, interval="Monthly"):
	date = getdate(date)
	months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
	return {
		"Daily": date.strftime("%d-%m-%y"),
		"Weekly": date.strftime("%d-%m-%y"),
		"Monthly": str(months[date.month - 1]) + " " + str(date.year),
		"Quarterly": "Quarter " + str(((date.month - 1) // 3) + 1) + " " + str(date.year),
		"Yearly": str(date.year),
	}[interval]


def get_period_beginning(date, timegrain, as_str=True):
	return getdate(
		{
			"Daily": date,
			"Weekly": get_first_day_of_week(date),
			"Monthly": get_first_day(date),
			"Quarterly": get_quarter_start(date),
			"Yearly": get_year_start(date),
		}[timegrain]
	)


def get_period_ending(date, timegrain):
	return getdate(
		{
			"Daily": date,
			"Weekly": get_last_day_of_week(date),
			"Monthly": get_last_day(date),
			"Quarterly": get_quarter_ending(date),
			"Yearly": get_year_ending(date),
		}[timegrain]
	)
