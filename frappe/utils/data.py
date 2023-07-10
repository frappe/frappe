# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import base64
import datetime
import json
import math
import operator
import re
import time
import typing
from code import compile_command
from enum import Enum
from typing import Any, Literal, Optional, TypeVar, Union
from urllib.parse import quote, urljoin

from click import secho
from dateutil import parser
from dateutil.parser import ParserError
from dateutil.relativedelta import relativedelta

import frappe
from frappe.desk.utils import slug
from frappe.utils.deprecations import deprecation_warning

DateTimeLikeObject = Union[str, datetime.date, datetime.datetime]
NumericType = Union[int, float]


if typing.TYPE_CHECKING:
	T = TypeVar("T")


DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S.%f"
DATETIME_FORMAT = f"{DATE_FORMAT} {TIME_FORMAT}"
TIMEDELTA_DAY_PATTERN = re.compile(
	r"(?P<days>[-\d]+) day[s]*, (?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d[\.\d+]*)"
)
TIMEDELTA_BASE_PATTERN = re.compile(r"(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d[\.\d+]*)")
URLS_HTTP_TAG_PATTERN = re.compile(
	r'(href|src){1}([\s]*=[\s]*[\'"]?)((?:http)[^\'">]+)([\'"]?)'
)  # href='https://...
URLS_NOT_HTTP_TAG_PATTERN = re.compile(
	r'(href|src){1}([\s]*=[\s]*[\'"]?)((?!http)[^\'" >]+)([\'"]?)'
)  # href=/assets/...
URL_NOTATION_PATTERN = re.compile(
	r'(:[\s]?url)(\([\'"]?)((?!http)[^\'" >]+)([\'"]?\))'
)  # background-image: url('/assets/...')
DURATION_PATTERN = re.compile(r"^(?:(\d+d)?((^|\s)\d+h)?((^|\s)\d+m)?((^|\s)\d+s)?)$")
HTML_TAG_PATTERN = re.compile("<[^>]+>")
MARIADB_SPECIFIC_COMMENT = re.compile(r"#.*")


class Weekday(Enum):
	Sunday = 0
	Monday = 1
	Tuesday = 2
	Wednesday = 3
	Thursday = 4
	Friday = 5
	Saturday = 6


def get_first_day_of_the_week() -> str:
	return frappe.get_system_settings("first_day_of_the_week") or "Sunday"


def get_start_of_week_index() -> int:
	return Weekday[get_first_day_of_the_week()].value


def is_invalid_date_string(date_string: str) -> bool:
	# dateutil parser does not agree with dates like "0001-01-01" or "0000-00-00"
	return not isinstance(date_string, str) or (
		(not date_string) or (date_string or "").startswith(("0001-01-01", "0000-00-00"))
	)


def getdate(
	string_date: Optional["DateTimeLikeObject"] = None, parse_day_first: bool = False
) -> datetime.date | None:
	"""
	Converts string date (yyyy-mm-dd) to datetime.date object.
	If no input is provided, current date is returned.
	"""
	if not string_date:
		return get_datetime().date()
	if isinstance(string_date, datetime.datetime):
		return string_date.date()

	elif isinstance(string_date, datetime.date):
		return string_date

	if is_invalid_date_string(string_date):
		return None
	try:
		return parser.parse(string_date, dayfirst=parse_day_first).date()
	except ParserError:
		frappe.throw(
			frappe._("{} is not a valid date string.").format(frappe.bold(string_date)),
			title=frappe._("Invalid Date"),
		)


def get_datetime(
	datetime_str: Optional["DateTimeLikeObject"] = None,
) -> datetime.datetime | None:

	if datetime_str is None:
		return now_datetime()

	if isinstance(datetime_str, (datetime.datetime, datetime.timedelta)):
		return datetime_str

	elif isinstance(datetime_str, (list, tuple)):
		return datetime.datetime(datetime_str)

	elif isinstance(datetime_str, datetime.date):
		return datetime.datetime.combine(datetime_str, datetime.time())

	if is_invalid_date_string(datetime_str):
		return None

	try:
		return datetime.datetime.strptime(datetime_str, DATETIME_FORMAT)
	except ValueError:
		return parser.parse(datetime_str)


def get_timedelta(time: str | None = None) -> datetime.timedelta | None:
	"""Return `datetime.timedelta` object from string value of a
	valid time format. Returns None if `time` is not a valid format

	Args:
	        time (str): A valid time representation. This string is parsed
	        using `dateutil.parser.parse`. Examples of valid inputs are:
	        '0:0:0', '17:21:00', '2012-01-19 17:21:00'. Checkout
	        https://dateutil.readthedocs.io/en/stable/parser.html#dateutil.parser.parse

	Returns:
	        datetime.timedelta: Timedelta object equivalent of the passed `time` string
	"""
	time = time or "0:0:0"

	try:
		try:
			t = parser.parse(time)
		except ParserError as e:
			if "day" in e.args[1] or "hour must be in" in e.args[0]:
				return parse_timedelta(time)
			raise e
		return datetime.timedelta(
			hours=t.hour, minutes=t.minute, seconds=t.second, microseconds=t.microsecond
		)
	except Exception:
		return None


def to_timedelta(time_str: str | datetime.time) -> datetime.timedelta:
	if isinstance(time_str, datetime.time):
		time_str = str(time_str)

	if isinstance(time_str, str):
		t = parser.parse(time_str)
		return datetime.timedelta(
			hours=t.hour, minutes=t.minute, seconds=t.second, microseconds=t.microsecond
		)

	else:
		return time_str


@typing.overload
def add_to_date(
	date,
	years=0,
	months=0,
	weeks=0,
	days=0,
	hours=0,
	minutes=0,
	seconds=0,
	as_string: Literal[False] = False,
	as_datetime: Literal[False] = False,
) -> datetime.date:
	...


@typing.overload
def add_to_date(
	date,
	years=0,
	months=0,
	weeks=0,
	days=0,
	hours=0,
	minutes=0,
	seconds=0,
	as_string: Literal[False] = False,
	as_datetime: Literal[True] = True,
) -> datetime.datetime:
	...


@typing.overload
def add_to_date(
	date,
	years=0,
	months=0,
	weeks=0,
	days=0,
	hours=0,
	minutes=0,
	seconds=0,
	as_string: Literal[True] = True,
	as_datetime: bool = False,
) -> str:
	...


def add_to_date(
	date: DateTimeLikeObject,
	years=0,
	months=0,
	weeks=0,
	days=0,
	hours=0,
	minutes=0,
	seconds=0,
	as_string=False,
	as_datetime=False,
) -> DateTimeLikeObject:
	"""Adds `days` to the given date"""

	if date is None:
		date = now_datetime()

	if hours:
		as_datetime = True

	if isinstance(date, str):
		as_string = True
		if " " in date:
			as_datetime = True
		try:
			date = parser.parse(date)
		except ParserError:
			frappe.throw(frappe._("Please select a valid date filter"), title=frappe._("Invalid Date"))

	date = date + relativedelta(
		years=years, months=months, weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds
	)

	if as_string:
		if as_datetime:
			return date.strftime(DATETIME_FORMAT)
		else:
			return date.strftime(DATE_FORMAT)
	else:
		return date


def add_days(date, days):
	return add_to_date(date, days=days)


def add_months(date, months):
	return add_to_date(date, months=months)


def add_years(date, years):
	return add_to_date(date, years=years)


def date_diff(string_ed_date, string_st_date):
	return (getdate(string_ed_date) - getdate(string_st_date)).days


def month_diff(string_ed_date, string_st_date):
	ed_date = getdate(string_ed_date)
	st_date = getdate(string_st_date)
	return (ed_date.year - st_date.year) * 12 + ed_date.month - st_date.month + 1


def time_diff(string_ed_date, string_st_date):
	return get_datetime(string_ed_date) - get_datetime(string_st_date)


def time_diff_in_seconds(string_ed_date, string_st_date):
	return time_diff(string_ed_date, string_st_date).total_seconds()


def time_diff_in_hours(string_ed_date, string_st_date):
	return round(float(time_diff(string_ed_date, string_st_date).total_seconds()) / 3600, 6)


def now_datetime():
	dt = convert_utc_to_system_timezone(datetime.datetime.utcnow())
	return dt.replace(tzinfo=None)


def get_timestamp(date):
	return time.mktime(getdate(date).timetuple())


def get_eta(from_time, percent_complete):
	diff = time_diff(now_datetime(), from_time).total_seconds()
	return str(datetime.timedelta(seconds=(100 - percent_complete) / percent_complete * diff))


def _get_system_timezone():
	return frappe.db.get_system_setting("time_zone") or "Asia/Kolkata"  # Default to India ?!


def get_system_timezone():
	if frappe.local.flags.in_test:
		return _get_system_timezone()

	return frappe.cache().get_value("time_zone", _get_system_timezone)


def get_time_zone():
	deprecation_warning(
		"`get_time_zone` is deprecated and will be removed in version 15. Use `get_system_timezone` instead."
	)
	return get_system_timezone()


def convert_utc_to_timezone(utc_timestamp, time_zone):
	from pytz import UnknownTimeZoneError, timezone

	utcnow = timezone("UTC").localize(utc_timestamp)
	try:
		return utcnow.astimezone(timezone(time_zone))
	except UnknownTimeZoneError:
		return utcnow


def get_datetime_in_timezone(time_zone):
	utc_timestamp = datetime.datetime.utcnow()
	return convert_utc_to_timezone(utc_timestamp, time_zone)


def convert_utc_to_system_timezone(utc_timestamp):
	time_zone = get_system_timezone()
	return convert_utc_to_timezone(utc_timestamp, time_zone)


def convert_utc_to_user_timezone(utc_timestamp):
	deprecation_warning(
		"`convert_utc_to_user_timezone` is deprecated and will be removed in version 15. Use `convert_utc_to_system_timezone` instead."
	)
	return convert_utc_to_system_timezone(utc_timestamp)


def now() -> str:
	"""return current datetime as yyyy-mm-dd hh:mm:ss"""
	if frappe.flags.current_date:
		return (
			getdate(frappe.flags.current_date).strftime(DATE_FORMAT)
			+ " "
			+ now_datetime().strftime(TIME_FORMAT)
		)
	else:
		return now_datetime().strftime(DATETIME_FORMAT)


def nowdate() -> str:
	"""return current date as yyyy-mm-dd"""
	return now_datetime().strftime(DATE_FORMAT)


def today() -> str:
	return nowdate()


def get_abbr(string: str, max_len: int = 2) -> str:
	abbr = ""
	for part in string.split(" "):
		if len(abbr) < max_len and part:
			abbr += part[0]

	return abbr or "?"


def nowtime() -> str:
	"""return current time in hh:mm"""
	return now_datetime().strftime(TIME_FORMAT)


@typing.overload
def get_first_day(dt, d_years=0, d_months=0, as_str: Literal[False] = False) -> datetime.date:
	...


@typing.overload
def get_first_day(dt, d_years=0, d_months=0, as_str: Literal[True] = False) -> str:
	...


# TODO: first arg
def get_first_day(
	dt, d_years: int = 0, d_months: int = 0, as_str: bool = False
) -> str | datetime.date:
	"""
	Returns the first day of the month for the date specified by date object
	Also adds `d_years` and `d_months` if specified
	"""
	dt = getdate(dt)

	# d_years, d_months are "deltas" to apply to dt
	overflow_years, month = divmod(dt.month + d_months - 1, 12)
	year = dt.year + d_years + overflow_years

	return (
		datetime.date(year, month + 1, 1).strftime(DATE_FORMAT)
		if as_str
		else datetime.date(year, month + 1, 1)
	)


@typing.overload
def get_quarter_start(dt, as_str: Literal[False] = False) -> datetime.date:
	...


@typing.overload
def get_quarter_start(dt, as_str: Literal[True] = False) -> str:
	...


def get_quarter_start(dt, as_str: bool = False) -> str | datetime.date:
	date = getdate(dt)
	quarter = (date.month - 1) // 3 + 1
	first_date_of_quarter = datetime.date(date.year, ((quarter - 1) * 3) + 1, 1)
	return first_date_of_quarter.strftime(DATE_FORMAT) if as_str else first_date_of_quarter


def get_first_day_of_week(dt, as_str=False):
	dt = getdate(dt)
	date = dt - datetime.timedelta(days=get_week_start_offset_days(dt))
	return date.strftime(DATE_FORMAT) if as_str else date


def get_week_start_offset_days(dt):
	current_day_index = get_normalized_weekday_index(dt)
	start_of_week_index = get_start_of_week_index()

	if current_day_index >= start_of_week_index:
		return current_day_index - start_of_week_index
	else:
		return 7 - (start_of_week_index - current_day_index)


def get_normalized_weekday_index(dt):
	# starts Sunday with 0
	return (dt.weekday() + 1) % 7


def get_year_start(dt, as_str=False):
	dt = getdate(dt)
	date = datetime.date(dt.year, 1, 1)
	return date.strftime(DATE_FORMAT) if as_str else date


def get_last_day_of_week(dt):
	dt = get_first_day_of_week(dt)
	return dt + datetime.timedelta(days=6)


def get_last_day(dt):
	"""
	Returns last day of the month using:
	`get_first_day(dt, 0, 1) + datetime.timedelta(-1)`
	"""
	return get_first_day(dt, 0, 1) + datetime.timedelta(-1)


def get_quarter_ending(date):
	date = getdate(date)

	# find the earliest quarter ending date that is after
	# the given date
	for month in (3, 6, 9, 12):
		quarter_end_month = getdate(f"{date.year}-{month}-01")
		quarter_end_date = getdate(get_last_day(quarter_end_month))
		if date <= quarter_end_date:
			date = quarter_end_date
			break

	return date


def get_year_ending(date):
	"""returns year ending of the given date"""
	date = getdate(date)
	# first day of next year (note year starts from 1)
	date = add_to_date(f"{date.year}-01-01", months=12)
	# last day of this month
	return add_to_date(date, days=-1)


def get_time(time_str: str) -> datetime.time:
	if isinstance(time_str, datetime.datetime):
		return time_str.time()
	elif isinstance(time_str, datetime.time):
		return time_str
	elif isinstance(time_str, datetime.timedelta):
		return (datetime.datetime.min + time_str).time()
	try:
		return parser.parse(time_str).time()
	except ParserError as e:
		if "day" in e.args[1] or "hour must be in" in e.args[0]:
			return (datetime.datetime.min + parse_timedelta(time_str)).time()
		raise e


def get_datetime_str(datetime_obj) -> str:
	if isinstance(datetime_obj, str):
		datetime_obj = get_datetime(datetime_obj)
	return datetime_obj.strftime(DATETIME_FORMAT)


def get_date_str(date_obj) -> str:
	if isinstance(date_obj, str):
		date_obj = get_datetime(date_obj)
	return date_obj.strftime(DATE_FORMAT)


def get_time_str(timedelta_obj) -> str:
	if isinstance(timedelta_obj, str):
		timedelta_obj = to_timedelta(timedelta_obj)

	hours, remainder = divmod(timedelta_obj.seconds, 3600)
	minutes, seconds = divmod(remainder, 60)
	return f"{hours}:{minutes}:{seconds}"


def get_user_date_format() -> str:
	"""Get the current user date format. The result will be cached."""
	if getattr(frappe.local, "user_date_format", None) is None:
		frappe.local.user_date_format = frappe.db.get_default("date_format")

	return frappe.local.user_date_format or "yyyy-mm-dd"


get_user_format = get_user_date_format  # for backwards compatibility


def get_user_time_format() -> str:
	"""Get the current user time format. The result will be cached."""
	if getattr(frappe.local, "user_time_format", None) is None:
		frappe.local.user_time_format = frappe.db.get_default("time_format")

	return frappe.local.user_time_format or "HH:mm:ss"


def format_date(
	string_date=None, format_string: str | None = None, parse_day_first: bool = False
) -> str:
	"""Converts the given string date to :data:`user_date_format`
	User format specified in defaults

	Examples:

	* dd-mm-yyyy
	* mm-dd-yyyy
	* dd/mm/yyyy
	"""
	import babel.dates
	from babel.core import UnknownLocaleError

	if not string_date:
		return ""

	date = getdate(string_date, parse_day_first)
	if not format_string:
		format_string = get_user_date_format()
	format_string = format_string.replace("mm", "MM").replace("Y", "y")
	try:
		formatted_date = babel.dates.format_date(
			date, format_string, locale=(frappe.local.lang or "").replace("-", "_")
		)
	except UnknownLocaleError:
		format_string = format_string.replace("MM", "%m").replace("dd", "%d").replace("yyyy", "%Y")
		formatted_date = date.strftime(format_string)
	return formatted_date


formatdate = format_date  # For backwards compatibility


def format_time(time_string=None, format_string: str | None = None) -> str:
	"""Converts the given string time to :data:`user_time_format`
	User format specified in defaults

	Examples:

	* HH:mm:ss
	* HH:mm
	"""
	import babel.dates
	from babel.core import UnknownLocaleError

	if not time_string:
		return ""

	time_ = get_time(time_string)
	if not format_string:
		format_string = get_user_time_format()
	try:
		formatted_time = babel.dates.format_time(
			time_, format_string, locale=(frappe.local.lang or "").replace("-", "_")
		)
	except UnknownLocaleError:
		formatted_time = time_.strftime("%H:%M:%S")
	return formatted_time


def format_datetime(datetime_string: DateTimeLikeObject, format_string: str | None = None) -> str:
	"""Converts the given string time to :data:`user_datetime_format`
	User format specified in defaults

	Examples:

	* dd-mm-yyyy HH:mm:ss
	* mm-dd-yyyy HH:mm
	"""
	import babel.dates
	from babel.core import UnknownLocaleError

	if not datetime_string:
		return

	datetime = get_datetime(datetime_string)
	if not format_string:
		format_string = get_user_date_format().replace("mm", "MM") + " " + get_user_time_format()

	try:
		formatted_datetime = babel.dates.format_datetime(
			datetime, format_string, locale=(frappe.local.lang or "").replace("-", "_")
		)
	except UnknownLocaleError:
		formatted_datetime = datetime.strftime("%Y-%m-%d %H:%M:%S")
	return formatted_datetime


def format_duration(seconds, hide_days=False):
	"""Converts the given duration value in float(seconds) to duration format

	example: converts 12885 to '3h 34m 45s' where 12885 = seconds in float
	"""

	seconds = cint(seconds)

	total_duration = {
		"days": math.floor(seconds / (3600 * 24)),
		"hours": math.floor(seconds % (3600 * 24) / 3600),
		"minutes": math.floor(seconds % 3600 / 60),
		"seconds": math.floor(seconds % 60),
	}

	if hide_days:
		total_duration["hours"] = math.floor(seconds / 3600)
		total_duration["days"] = 0

	duration = ""
	if total_duration:
		if total_duration.get("days"):
			duration += str(total_duration.get("days")) + "d"
		if total_duration.get("hours"):
			duration += " " if len(duration) else ""
			duration += str(total_duration.get("hours")) + "h"
		if total_duration.get("minutes"):
			duration += " " if len(duration) else ""
			duration += str(total_duration.get("minutes")) + "m"
		if total_duration.get("seconds"):
			duration += " " if len(duration) else ""
			duration += str(total_duration.get("seconds")) + "s"

	return duration


def duration_to_seconds(duration):
	"""Converts the given duration formatted value to duration value in seconds

	example: converts '3h 34m 45s' to 12885 (value in seconds)
	"""
	validate_duration_format(duration)
	value = 0
	if "d" in duration:
		val = duration.split("d")
		days = val[0]
		value += cint(days) * 24 * 60 * 60
		duration = val[1]
	if "h" in duration:
		val = duration.split("h")
		hours = val[0]
		value += cint(hours) * 60 * 60
		duration = val[1]
	if "m" in duration:
		val = duration.split("m")
		mins = val[0]
		value += cint(mins) * 60
		duration = val[1]
	if "s" in duration:
		val = duration.split("s")
		secs = val[0]
		value += cint(secs)

	return value


def validate_duration_format(duration):
	if not DURATION_PATTERN.match(duration):
		frappe.throw(
			frappe._("Value {0} must be in the valid duration format: d h m s").format(
				frappe.bold(duration)
			)
		)


def get_weekdays():
	return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get_weekday(datetime: datetime.datetime | None = None) -> str:
	if not datetime:
		datetime = now_datetime()
	weekdays = get_weekdays()
	return weekdays[datetime.weekday()]


def get_timespan_date_range(timespan: str) -> tuple[datetime.datetime, datetime.datetime]:
	today = nowdate()
	date_range_map = {
		"last week": lambda: (
			get_first_day_of_week(add_to_date(today, days=-7)),
			get_last_day_of_week(add_to_date(today, days=-7)),
		),
		"last month": lambda: (
			get_first_day(add_to_date(today, months=-1)),
			get_last_day(add_to_date(today, months=-1)),
		),
		"last quarter": lambda: (
			get_quarter_start(add_to_date(today, months=-3)),
			get_quarter_ending(add_to_date(today, months=-3)),
		),
		"last 6 months": lambda: (
			get_quarter_start(add_to_date(today, months=-6)),
			get_quarter_ending(add_to_date(today, months=-3)),
		),
		"last year": lambda: (
			get_year_start(add_to_date(today, years=-1)),
			get_year_ending(add_to_date(today, years=-1)),
		),
		"yesterday": lambda: (add_to_date(today, days=-1),) * 2,
		"today": lambda: (today, today),
		"tomorrow": lambda: (add_to_date(today, days=1),) * 2,
		"this week": lambda: (get_first_day_of_week(today), get_last_day_of_week(today)),
		"this month": lambda: (get_first_day(today), get_last_day(today)),
		"this quarter": lambda: (get_quarter_start(today), get_quarter_ending(today)),
		"this year": lambda: (get_year_start(today), get_year_ending(today)),
		"next week": lambda: (
			get_first_day_of_week(add_to_date(today, days=7)),
			get_last_day_of_week(add_to_date(today, days=7)),
		),
		"next month": lambda: (
			get_first_day(add_to_date(today, months=1)),
			get_last_day(add_to_date(today, months=1)),
		),
		"next quarter": lambda: (
			get_quarter_start(add_to_date(today, months=3)),
			get_quarter_ending(add_to_date(today, months=3)),
		),
		"next 6 months": lambda: (
			get_quarter_start(add_to_date(today, months=3)),
			get_quarter_ending(add_to_date(today, months=6)),
		),
		"next year": lambda: (
			get_year_start(add_to_date(today, years=1)),
			get_year_ending(add_to_date(today, years=1)),
		),
	}

	if timespan in date_range_map:
		return date_range_map[timespan]()


def global_date_format(date, format="long"):
	"""returns localized date in the form of January 1, 2012"""
	import babel.dates

	date = getdate(date)
	formatted_date = babel.dates.format_date(
		date, locale=(frappe.local.lang or "en").replace("-", "_"), format=format
	)
	return formatted_date


def has_common(l1: typing.Hashable, l2: typing.Hashable) -> bool:
	"""Returns truthy value if there are common elements in lists l1 and l2"""
	return set(l1) & set(l2)


def cast_fieldtype(fieldtype, value, show_warning=True):
	if show_warning:
		message = (
			"Function `frappe.utils.data.cast_fieldtype` has been deprecated in favour"
			" of `frappe.utils.data.cast`. Use the newer util for safer type casting."
		)
		secho(message, fg="yellow")

	if fieldtype in ("Currency", "Float", "Percent"):
		value = flt(value)

	elif fieldtype in ("Int", "Check"):
		value = cint(value)

	elif fieldtype in (
		"Data",
		"Text",
		"Small Text",
		"Long Text",
		"Text Editor",
		"Select",
		"Link",
		"Dynamic Link",
	):
		value = cstr(value)

	elif fieldtype == "Date":
		value = getdate(value)

	elif fieldtype == "Datetime":
		value = get_datetime(value)

	elif fieldtype == "Time":
		value = to_timedelta(value)

	return value


def cast(fieldtype, value=None):
	"""Cast the value to the Python native object of the Frappe fieldtype provided.
	If value is None, the first/lowest value of the `fieldtype` will be returned.
	If value can't be cast as fieldtype due to an invalid input, None will be returned.

	Mapping of Python types => Frappe types:
	        * str => ("Data", "Text", "Small Text", "Long Text", "Text Editor", "Select", "Link", "Dynamic Link")
	        * float => ("Currency", "Float", "Percent")
	        * int => ("Int", "Check")
	        * datetime.datetime => ("Datetime",)
	        * datetime.date => ("Date",)
	        * datetime.time => ("Time",)
	"""
	if fieldtype in ("Currency", "Float", "Percent"):
		value = flt(value)

	elif fieldtype in ("Int", "Check"):
		value = cint(sbool(value))

	elif fieldtype in (
		"Data",
		"Text",
		"Small Text",
		"Long Text",
		"Text Editor",
		"Select",
		"Link",
		"Dynamic Link",
	):
		value = cstr(value)

	elif fieldtype == "Date":
		if value:
			value = getdate(value)
		else:
			value = datetime.datetime(1, 1, 1).date()

	elif fieldtype == "Datetime":
		if value:
			value = get_datetime(value)
		else:
			value = datetime.datetime(1, 1, 1)

	elif fieldtype == "Time":
		value = get_timedelta(value)

	return value


@typing.overload
def flt(s: NumericType | str, precision: Literal[0]) -> int:
	...


@typing.overload
def flt(s: NumericType | str, precision: int | None = None) -> float:
	...


def flt(
	s: NumericType | str, precision: int | None = None, rounding_method: str | None = None
) -> float:
	"""Convert to float (ignoring commas in string)

	:param s: Number in string or other numeric format.
	:param precision: optional argument to specify precision for rounding.
	:returns: Converted number in python float type.

	Returns 0 if input can not be converted to float.

	Examples:

	>>> flt("43.5", precision=0)
	44
	>>> flt("42.5", precision=0)
	42
	>>> flt("10,500.5666", precision=2)
	10500.57
	>>> flt("a")
	0.0
	"""
	if isinstance(s, str):
		s = s.replace(",", "")

	try:
		num = float(s)
		if precision is not None:
			num = rounded(num, precision, rounding_method)
	except Exception as e:
		if isinstance(e, frappe.InvalidRoundingMethod):
			raise
		num = 0.0

	return num


def cint(s: NumericType | str, default: int = 0) -> int:
	"""Convert to integer

	:param s: Number in string or other numeric format.
	:returns: Converted number in python integer type.

	Returns default if input can not be converted to integer.

	Examples:
	>>> cint("100")
	100
	>>> cint("a")
	0

	"""
	try:
		return int(float(s))
	except Exception:
		return default


def floor(s):
	"""
	A number representing the largest integer less than or equal to the specified number

	Parameters
	----------
	s : int or str or Decimal object
	        The mathematical value to be floored

	Returns
	-------
	int
	        number representing the largest integer less than or equal to the specified number

	"""
	try:
		num = cint(math.floor(flt(s)))
	except Exception:
		num = 0
	return num


def ceil(s):
	"""
	The smallest integer greater than or equal to the given number

	Parameters
	----------
	s : int or str or Decimal object
	        The mathematical value to be ceiled

	Returns
	-------
	int
	        smallest integer greater than or equal to the given number

	"""
	try:
		num = cint(math.ceil(flt(s)))
	except Exception:
		num = 0
	return num


def cstr(s, encoding="utf-8"):
	return frappe.as_unicode(s, encoding)


def sbool(x: str) -> bool | Any:
	"""Converts str object to Boolean if possible.
	Example:
	        "true" becomes True
	        "1" becomes True
	        "{}" remains "{}"

	Args:
	        x (str): String to be converted to Bool

	Returns:
	        object: Returns Boolean or x
	"""
	try:
		val = x.lower()
		if val in ("true", "1"):
			return True
		elif val in ("false", "0"):
			return False
		return x
	except Exception:
		return x


def rounded(num, precision=0, rounding_method=None):
	"""Round according to method set in system setting, defaults to banker's rounding"""
	precision = cint(precision)

	rounding_method = (
		rounding_method or frappe.get_system_settings("rounding_method") or "Banker's Rounding (legacy)"
	)

	if rounding_method == "Banker's Rounding (legacy)":
		return _bankers_rounding_legacy(num, precision)
	elif rounding_method == "Banker's Rounding":
		return _bankers_rounding(num, precision)
	elif rounding_method == "Commercial Rounding":
		return _round_away_from_zero(num, precision)
	else:
		frappe.throw(
			frappe._("Unknown Rounding Method: {}").format(rounding_method),
			exc=frappe.InvalidRoundingMethod,
		)


def _bankers_rounding_legacy(num, precision):
	# avoid rounding errors
	multiplier = 10**precision
	num = round(num * multiplier if precision else num, 8)

	floor_num = math.floor(num)
	decimal_part = num - floor_num

	if not precision and decimal_part == 0.5:
		num = floor_num if (floor_num % 2 == 0) else floor_num + 1
	else:
		if decimal_part == 0.5:
			num = floor_num + 1
		else:
			num = round(num)

	return (num / multiplier) if precision else num


def _round_away_from_zero(num, precision):
	if num == 0:
		return 0.0

	# Epsilon is small correctional value added to correctly round numbers which can't be
	# represented in IEEE 754 representation.

	# In simplified terms, the representation optimizes for absolute errors in representation
	# so if a number is not representable it might be represented by a value ever so slighly
	# smaller than the value itself. This becomes a problem when breaking ties for numbers
	# ending with 5 when it's represented by a smaller number. By adding a very small value
	# close to what's "least count" or smallest representable difference in the scale we force
	# the number to be bigger than actual value, this increases representation error but
	# removes rounding error.

	# References:
	# - https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html
	# - https://docs.python.org/3/tutorial/floatingpoint.html#representation-error
	# - https://docs.python.org/3/library/functions.html#round
	# - easier to understand: https://www.youtube.com/watch?v=pQs_wx8eoQ8

	epsilon = 2.0 ** (math.log(abs(num), 2) - 52.0)

	return round(num + math.copysign(epsilon, num), precision)


def _bankers_rounding(num, precision):
	multiplier = 10**precision
	num = round(num * multiplier, 12)

	if num == 0:
		return 0.0

	floor_num = math.floor(num)
	decimal_part = num - floor_num

	epsilon = 2.0 ** (math.log(abs(num), 2) - 52.0)
	if abs(decimal_part - 0.5) < epsilon:
		num = floor_num if (floor_num % 2 == 0) else floor_num + 1
	else:
		num = round(num)

	return num / multiplier


def remainder(numerator: NumericType, denominator: NumericType, precision: int = 2) -> NumericType:
	precision = cint(precision)
	multiplier = 10**precision

	if precision:
		_remainder = ((numerator * multiplier) % (denominator * multiplier)) / multiplier
	else:
		_remainder = numerator % denominator

	return flt(_remainder, precision)


def safe_div(numerator: NumericType, denominator: NumericType, precision: int = 2) -> float:
	"""
	SafeMath division that returns zero when divided by zero.
	"""
	precision = cint(precision)

	if denominator == 0:
		_res = 0.0
	else:
		_res = float(numerator) / denominator

	return flt(_res, precision)


def round_based_on_smallest_currency_fraction(value, currency, precision=2):
	smallest_currency_fraction_value = flt(
		frappe.db.get_value("Currency", currency, "smallest_currency_fraction_value", cache=True)
	)

	if smallest_currency_fraction_value:
		remainder_val = remainder(value, smallest_currency_fraction_value, precision)
		if remainder_val > (smallest_currency_fraction_value / 2):
			value += smallest_currency_fraction_value - remainder_val
		else:
			value -= remainder_val
	else:
		value = rounded(value)

	return flt(value, precision)


def encode(obj, encoding="utf-8"):
	if isinstance(obj, list):
		out = []
		for o in obj:
			if isinstance(o, str):
				out.append(o.encode(encoding))
			else:
				out.append(o)
		return out
	elif isinstance(obj, str):
		return obj.encode(encoding)
	else:
		return obj


def parse_val(v):
	"""Converts to simple datatypes from SQL query results"""
	if isinstance(v, (datetime.date, datetime.datetime)):
		v = str(v)
	elif isinstance(v, datetime.timedelta):
		v = ":".join(str(v).split(":")[:2])
	elif isinstance(v, int):
		v = int(v)
	return v


def fmt_money(
	amount: str | float | int | None,
	precision: int | None = None,
	currency: str | None = None,
	format: str | None = None,
) -> str:
	"""
	Convert to string with commas for thousands, millions etc
	"""
	number_format = format or frappe.db.get_default("number_format") or "#,###.##"
	if precision is None:
		precision = cint(frappe.db.get_default("currency_precision")) or None

	decimal_str, comma_str, number_format_precision = get_number_format_info(number_format)

	if precision is None:
		precision = number_format_precision

	# 40,000 -> 40,000.00
	# 40,000.00000 -> 40,000.00
	# 40,000.23000 -> 40,000.23

	if isinstance(amount, str):
		amount = flt(amount, precision)

	if amount is None:
		amount = 0

	if decimal_str:
		decimals_after = str(round(amount % 1, precision))
		parts = decimals_after.split(".")
		parts = parts[1] if len(parts) > 1 else parts[0]
		decimals = parts
		if precision > 2:
			if len(decimals) < 3:
				if currency:
					fraction = frappe.db.get_value("Currency", currency, "fraction_units", cache=True) or 100
					precision = len(cstr(fraction)) - 1
				else:
					precision = number_format_precision
			elif len(decimals) < precision:
				precision = len(decimals)

	amount = "%.*f" % (precision, round(flt(amount), precision))

	if amount.find(".") == -1:
		decimals = ""
	else:
		decimals = amount.split(".")[1]

	parts = []
	minus = ""
	if flt(amount) < 0:
		minus = "-"

	amount = cstr(abs(flt(amount))).split(".", 1)[0]

	if len(amount) > 3:
		parts.append(amount[-3:])
		amount = amount[:-3]

		val = number_format == "#,##,###.##" and 2 or 3

		while len(amount) > val:
			parts.append(amount[-val:])
			amount = amount[:-val]

	parts.append(amount)

	parts.reverse()

	amount = comma_str.join(parts) + ((precision and decimal_str) and (decimal_str + decimals) or "")
	if amount != "0":
		amount = minus + amount

	if currency and frappe.defaults.get_global_default("hide_currency_symbol") != "Yes":
		symbol = frappe.db.get_value("Currency", currency, "symbol", cache=True) or currency
		symbol_on_right = frappe.db.get_value("Currency", currency, "symbol_on_right", cache=True)

		if symbol_on_right:
			amount = f"{amount} {frappe._(symbol)}"
		else:
			amount = f"{frappe._(symbol)} {amount}"

	return amount


number_format_info = {
	"#,###.##": (".", ",", 2),
	"#.###,##": (",", ".", 2),
	"# ###.##": (".", " ", 2),
	"# ###,##": (",", " ", 2),
	"#'###.##": (".", "'", 2),
	"#, ###.##": (".", ", ", 2),
	"#,##,###.##": (".", ",", 2),
	"#,###.###": (".", ",", 3),
	"#.###": ("", ".", 0),
	"#,###": ("", ",", 0),
	"#.########": (".", "", 8),
}


def get_number_format_info(format: str) -> tuple[str, str, int]:
	return number_format_info.get(format) or (".", ",", 2)


#
# convert currency to words
#
def money_in_words(
	number: str | float | int,
	main_currency: str | None = None,
	fraction_currency: str | None = None,
):
	"""
	Returns string in words with currency and fraction currency.
	"""
	from frappe.utils import get_defaults

	_ = frappe._

	try:
		# note: `flt` returns 0 for invalid input and we don't want that
		number = float(number)
	except ValueError:
		return ""

	number = flt(number)
	if number < 0:
		return ""

	d = get_defaults()
	if not main_currency:
		main_currency = d.get("currency", "INR")
	if not fraction_currency:
		fraction_currency = frappe.db.get_value("Currency", main_currency, "fraction", cache=True) or _(
			"Cent"
		)

	number_format = (
		frappe.db.get_value("Currency", main_currency, "number_format", cache=True)
		or frappe.db.get_default("number_format")
		or "#,###.##"
	)

	fraction_length = get_number_format_info(number_format)[2]

	n = f"%.{fraction_length}f" % number

	numbers = n.split(".")
	main, fraction = numbers if len(numbers) > 1 else [n, "00"]

	if len(fraction) < fraction_length:
		zeros = "0" * (fraction_length - len(fraction))
		fraction += zeros

	in_million = True
	if number_format == "#,##,###.##":
		in_million = False

	# 0.00
	if main == "0" and fraction in ["00", "000"]:
		out = "{} {}".format(main_currency, _("Zero"))
	# 0.XX
	elif main == "0":
		out = _(in_words(fraction, in_million).title()) + " " + fraction_currency
	else:
		out = main_currency + " " + _(in_words(main, in_million).title())
		if cint(fraction):
			out = (
				out
				+ " "
				+ _("and")
				+ " "
				+ _(in_words(fraction, in_million).title())
				+ " "
				+ fraction_currency
			)

	return out + " " + _("only.")


#
# convert number to words
#
def in_words(integer: int, in_million=True) -> str:
	"""
	Returns string in words for the given integer.
	"""
	from num2words import num2words

	locale = "en_IN" if not in_million else frappe.local.lang
	integer = int(integer)
	try:
		ret = num2words(integer, lang=locale)
	except NotImplementedError:
		ret = num2words(integer, lang="en")
	except OverflowError:
		ret = num2words(integer, lang="en")
	return ret.replace("-", " ")


def is_html(text: str) -> bool:
	if not isinstance(text, str):
		return False
	return HTML_TAG_PATTERN.search(text)


def is_image(filepath: str) -> bool:
	from mimetypes import guess_type

	# filepath can be https://example.com/bed.jpg?v=129
	filepath = (filepath or "").split("?", 1)[0]
	return (guess_type(filepath)[0] or "").startswith("image/")


def get_thumbnail_base64_for_image(src):
	from os.path import exists as file_exists

	from PIL import Image

	from frappe import cache, safe_decode
	from frappe.core.doctype.file.utils import get_local_image

	if not src:
		frappe.throw(f"Invalid source for image: {src}")

	if not src.startswith("/files") or ".." in src:
		return

	if src.endswith(".svg"):
		return

	def _get_base64():
		file_path = frappe.get_site_path("public", src.lstrip("/"))
		if not file_exists(file_path):
			return

		try:
			image, unused_filename, extn = get_local_image(src)
		except OSError:
			return

		original_size = image.size
		size = 50, 50
		image.thumbnail(size, Image.Resampling.LANCZOS)

		base64_string = image_to_base64(image, extn)
		return {
			"base64": f"data:image/{extn};base64,{safe_decode(base64_string)}",
			"width": original_size[0],
			"height": original_size[1],
		}

	return cache().hget("thumbnail_base64", src, generator=_get_base64)


def image_to_base64(image, extn: str) -> bytes:
	from io import BytesIO

	buffered = BytesIO()
	if extn.lower() in ("jpg", "jpe"):
		extn = "JPEG"
	image.save(buffered, extn)
	img_str = base64.b64encode(buffered.getvalue())
	return img_str


def pdf_to_base64(filename: str) -> bytes | None:
	from frappe.utils.file_manager import get_file_path

	if "../" in filename or filename.rsplit(".")[-1] not in ["pdf", "PDF"]:
		return

	file_path = get_file_path(filename)
	if not file_path:
		return

	with open(file_path, "rb") as pdf_file:
		base64_string = base64.b64encode(pdf_file.read())

	return base64_string


# from Jinja2 code
_striptags_re = re.compile(r"(<!--.*?-->|<[^>]*>)")


def strip_html(text: str) -> str:
	"""removes anything enclosed in and including <>"""
	return _striptags_re.sub("", text)


def escape_html(text: str) -> str:
	if not isinstance(text, str):
		return text

	html_escape_table = {
		"&": "&amp;",
		'"': "&quot;",
		"'": "&apos;",
		">": "&gt;",
		"<": "&lt;",
	}

	return "".join(html_escape_table.get(c, c) for c in text)


def pretty_date(iso_datetime: datetime.datetime | str) -> str:
	"""
	Takes an ISO time and returns a string representing how
	long ago the date represents.
	Ported from PrettyDate by John Resig
	"""
	from frappe import _

	if not iso_datetime:
		return ""
	import math

	if isinstance(iso_datetime, str):
		iso_datetime = datetime.datetime.strptime(iso_datetime, DATETIME_FORMAT)
	now_dt = datetime.datetime.strptime(now(), DATETIME_FORMAT)
	dt_diff = now_dt - iso_datetime

	# available only in python 2.7+
	# dt_diff_seconds = dt_diff.total_seconds()

	dt_diff_seconds = dt_diff.days * 86400.0 + dt_diff.seconds

	dt_diff_days = math.floor(dt_diff_seconds / 86400.0)

	# differnt cases
	if dt_diff_seconds < 60.0:
		return _("just now")
	elif dt_diff_seconds < 120.0:
		return _("1 minute ago")
	elif dt_diff_seconds < 3600.0:
		return _("{0} minutes ago").format(cint(math.floor(dt_diff_seconds / 60.0)))
	elif dt_diff_seconds < 7200.0:
		return _("1 hour ago")
	elif dt_diff_seconds < 86400.0:
		return _("{0} hours ago").format(cint(math.floor(dt_diff_seconds / 3600.0)))
	elif dt_diff_days == 1.0:
		return _("Yesterday")
	elif dt_diff_days < 7.0:
		return _("{0} days ago").format(cint(dt_diff_days))
	elif dt_diff_days < 14:
		return _("1 week ago")
	elif dt_diff_days < 31.0:
		return _("{0} weeks ago").format(dt_diff_days // 7)
	elif dt_diff_days < 61.0:
		return _("1 month ago")
	elif dt_diff_days < 365.0:
		return _("{0} months ago").format(dt_diff_days // 30)
	elif dt_diff_days < 730.0:
		return _("1 year ago")
	else:
		return f"{cint(math.floor(dt_diff_days / 365.0))} years ago"


def comma_or(some_list, add_quotes=True):
	return comma_sep(some_list, frappe._("{0} or {1}"), add_quotes)


def comma_and(some_list, add_quotes=True):
	return comma_sep(some_list, frappe._("{0} and {1}"), add_quotes)


def comma_sep(some_list, pattern, add_quotes=True):
	if isinstance(some_list, (list, tuple)):
		# list(some_list) is done to preserve the existing list
		some_list = [str(s) for s in list(some_list)]
		if not some_list:
			return ""
		elif len(some_list) == 1:
			return some_list[0]
		else:
			some_list = ["'%s'" % s for s in some_list] if add_quotes else ["%s" % s for s in some_list]
			return pattern.format(", ".join(frappe._(s) for s in some_list[:-1]), some_list[-1])
	else:
		return some_list


def new_line_sep(some_list):
	if isinstance(some_list, (list, tuple)):
		# list(some_list) is done to preserve the existing list
		some_list = [str(s) for s in list(some_list)]
		if not some_list:
			return ""
		elif len(some_list) == 1:
			return some_list[0]
		else:
			some_list = ["%s" % s for s in some_list]
			return format("\n ".join(some_list))
	else:
		return some_list


def filter_strip_join(some_list: list[str], sep: str) -> list[str]:
	"""given a list, filter None values, strip spaces and join"""
	return (cstr(sep)).join(cstr(a).strip() for a in filter(None, some_list))


def get_url(uri: str | None = None, full_address: bool = False) -> str:
	"""get app url from request"""
	host_name = frappe.local.conf.host_name or frappe.local.conf.hostname

	if uri and (uri.startswith("http://") or uri.startswith("https://")):
		return uri

	if not host_name:
		request_host_name = get_host_name_from_request()

		if request_host_name:
			host_name = request_host_name

		elif frappe.local.site:
			protocol = "http://"

			if frappe.local.conf.ssl_certificate:
				protocol = "https://"

			elif frappe.local.conf.wildcard:
				domain = frappe.local.conf.wildcard.get("domain")
				if (
					domain
					and frappe.local.site.endswith(domain)
					and frappe.local.conf.wildcard.get("ssl_certificate")
				):
					protocol = "https://"

			host_name = protocol + frappe.local.site

		else:
			host_name = frappe.db.get_single_value("Website Settings", "subdomain")

			if not host_name:
				host_name = "http://localhost"

	if host_name and not (host_name.startswith("http://") or host_name.startswith("https://")):
		host_name = "http://" + host_name

	if not uri and full_address:
		uri = frappe.get_request_header("REQUEST_URI", "")

	port = frappe.conf.http_port or frappe.conf.webserver_port

	if (
		not (frappe.conf.restart_supervisor_on_update or frappe.conf.restart_systemd_on_update)
		and host_name
		and not url_contains_port(host_name)
		and port
	):
		host_name = host_name + ":" + str(port)

	url = urljoin(host_name, uri) if uri else host_name

	return url


def get_host_name_from_request() -> str:
	if hasattr(frappe.local, "request") and frappe.local.request and frappe.local.request.host:
		protocol = (
			"https://" if "https" == frappe.get_request_header("X-Forwarded-Proto", "") else "http://"
		)
		return protocol + frappe.local.request.host


def url_contains_port(url: str) -> bool:
	parts = url.split(":")
	return len(parts) > 2


def get_host_name() -> str:
	return get_url().rsplit("//", 1)[-1]


def get_link_to_form(doctype: str, name: str, label: str | None = None) -> str:
	if not label:
		label = name

	return f"""<a href="{get_url_to_form(doctype, name)}">{label}</a>"""


def get_link_to_report(
	name: str,
	label: str | None = None,
	report_type: str | None = None,
	doctype: str | None = None,
	filters: dict | None = None,
) -> str:
	if not label:
		label = name

	if filters:
		conditions = []
		for k, v in filters.items():
			if isinstance(v, list):
				for value in v:
					conditions.append(
						str(k) + "=" + '["' + str(value[0] + '"' + "," + '"' + str(value[1]) + '"]')
					)
			else:
				conditions.append(str(k) + "=" + str(v))

		filters = "&".join(conditions)

		return """<a href='{}'>{}</a>""".format(
			get_url_to_report_with_filters(name, filters, report_type, doctype), label
		)
	else:
		return f"""<a href='{get_url_to_report(name, report_type, doctype)}'>{label}</a>"""


def get_absolute_url(doctype: str, name: str) -> str:
	return f"/app/{quoted(slug(doctype))}/{quoted(name)}"


def get_url_to_form(doctype: str, name: str) -> str:
	return get_url(uri=f"/app/{quoted(slug(doctype))}/{quoted(name)}")


def get_url_to_list(doctype: str) -> str:
	return get_url(uri=f"/app/{quoted(slug(doctype))}")


def get_url_to_report(name, report_type: str | None = None, doctype: str | None = None) -> str:
	if report_type == "Report Builder":
		return get_url(uri=f"/app/{quoted(slug(doctype))}/view/report/{quoted(name)}")
	else:
		return get_url(uri=f"/app/query-report/{quoted(name)}")


def get_url_to_report_with_filters(name, filters, report_type=None, doctype=None):
	if report_type == "Report Builder":
		return get_url(uri=f"/app/{quoted(slug(doctype))}/view/report?{filters}")

	return get_url(uri=f"/app/query-report/{quoted(name)}?{filters}")


operator_map = {
	# startswith
	"^": lambda a, b: (a or "").startswith(b),
	# in or not in a list
	"in": lambda a, b: operator.contains(b, a),
	"not in": lambda a, b: not operator.contains(b, a),
	# comparison operators
	"=": lambda a, b: operator.eq(a, b),
	"!=": lambda a, b: operator.ne(a, b),
	">": lambda a, b: operator.gt(a, b),
	"<": lambda a, b: operator.lt(a, b),
	">=": lambda a, b: operator.ge(a, b),
	"<=": lambda a, b: operator.le(a, b),
	"not None": lambda a, b: a and True or False,
	"None": lambda a, b: (not a) and True or False,
}


def evaluate_filters(doc, filters: dict | list | tuple):
	"""Returns true if doc matches filters"""
	if isinstance(filters, dict):
		for key, value in filters.items():
			f = get_filter(None, {key: value})
			if not compare(doc.get(f.fieldname), f.operator, f.value, f.fieldtype):
				return False

	elif isinstance(filters, (list, tuple)):
		for d in filters:
			f = get_filter(None, d)
			if not compare(doc.get(f.fieldname), f.operator, f.value, f.fieldtype):
				return False

	return True


def compare(val1: Any, condition: str, val2: Any, fieldtype: str | None = None):
	ret = False
	if fieldtype:
		val1 = cast(fieldtype, val1)
		val2 = cast(fieldtype, val2)
	if condition in operator_map:
		ret = operator_map[condition](val1, val2)

	return ret


def get_filter(doctype: str, f: dict | list | tuple, filters_config=None) -> "frappe._dict":
	"""Returns a _dict like

	{
	        "doctype":
	        "fieldname":
	        "operator":
	        "value":
	        "fieldtype":
	}
	"""
	from frappe.model import child_table_fields, default_fields, optional_fields

	if isinstance(f, dict):
		key, value = next(iter(f.items()))
		f = make_filter_tuple(doctype, key, value)

	if not isinstance(f, (list, tuple)):
		frappe.throw(frappe._("Filter must be a tuple or list (in a list)"))

	if len(f) == 3:
		f = (doctype, f[0], f[1], f[2])
	elif len(f) > 4:
		f = f[0:4]
	elif len(f) != 4:
		frappe.throw(
			frappe._("Filter must have 4 values (doctype, fieldname, operator, value): {0}").format(str(f))
		)

	f = frappe._dict(doctype=f[0], fieldname=f[1], operator=f[2], value=f[3])

	sanitize_column(f.fieldname)

	if not f.operator:
		# if operator is missing
		f.operator = "="

	valid_operators = (
		"=",
		"!=",
		">",
		"<",
		">=",
		"<=",
		"like",
		"not like",
		"in",
		"not in",
		"is",
		"between",
		"descendants of",
		"ancestors of",
		"not descendants of",
		"not ancestors of",
		"timespan",
		"previous",
		"next",
	)

	if filters_config:
		additional_operators = []
		for key in filters_config:
			additional_operators.append(key.lower())
		valid_operators = tuple(set(valid_operators + tuple(additional_operators)))

	if f.operator.lower() not in valid_operators:
		frappe.throw(frappe._("Operator must be one of {0}").format(", ".join(valid_operators)))

	if f.doctype and (f.fieldname not in default_fields + optional_fields + child_table_fields):
		# verify fieldname belongs to the doctype
		meta = frappe.get_meta(f.doctype)
		if not meta.has_field(f.fieldname):

			# try and match the doctype name from child tables
			for df in meta.get_table_fields():
				if frappe.get_meta(df.options).has_field(f.fieldname):
					f.doctype = df.options
					break

	try:
		df = frappe.get_meta(f.doctype).get_field(f.fieldname)
	except frappe.exceptions.DoesNotExistError:
		df = None

	f.fieldtype = df.fieldtype if df else None

	return f


def make_filter_tuple(doctype, key, value):
	"""return a filter tuple like [doctype, key, operator, value]"""
	if isinstance(value, (list, tuple)):
		return [doctype, key, value[0], value[1]]
	else:
		return [doctype, key, "=", value]


def make_filter_dict(filters):
	"""convert this [[doctype, key, operator, value], ..]
	to this { key: (operator, value), .. }
	"""
	_filter = frappe._dict()
	for f in filters:
		_filter[f[1]] = (f[2], f[3])

	return _filter


def sanitize_column(column_name: str) -> None:
	import sqlparse

	from frappe import _

	column_name = sqlparse.format(column_name, strip_comments=True, keyword_case="lower")
	if frappe.db and frappe.db.db_type == "mariadb":
		# strip mariadb specific comments which are like python single line comments
		column_name = MARIADB_SPECIFIC_COMMENT.sub("", column_name)

	blacklisted_keywords = [
		"select",
		"create",
		"insert",
		"delete",
		"drop",
		"update",
		"case",
		"and",
		"or",
	]

	def _raise_exception():
		frappe.throw(_("Invalid field name {0}").format(column_name), frappe.DataError)

	regex = re.compile("^.*[,'();].*")
	if "ifnull" in column_name:
		if regex.match(column_name):
			# to avoid and, or
			if any(f" {keyword} " in column_name.split() for keyword in blacklisted_keywords):
				_raise_exception()

			# to avoid select, delete, drop, update and case
			elif any(keyword in column_name.split() for keyword in blacklisted_keywords):
				_raise_exception()

	elif regex.match(column_name):
		_raise_exception()


def scrub_urls(html: str) -> str:
	html = expand_relative_urls(html)
	# encoding should be responsibility of the composer
	# html = quote_urls(html)
	return html


def expand_relative_urls(html: str) -> str:
	# expand relative urls
	url = get_url()
	if url.endswith("/"):
		url = url[:-1]

	def _expand_relative_urls(match):
		to_expand = list(match.groups())

		if not to_expand[2].startswith(("mailto", "data:", "tel:")):
			if not to_expand[2].startswith("/"):
				to_expand[2] = "/" + to_expand[2]
			to_expand.insert(2, url)

		if "url" in to_expand[0] and to_expand[1].startswith("(") and to_expand[-1].endswith(")"):
			# background-image: url('/assets/...') - workaround for wkhtmltopdf print-media-type
			to_expand.append(" !important")

		return "".join(to_expand)

	html = URLS_NOT_HTTP_TAG_PATTERN.sub(_expand_relative_urls, html)
	html = URL_NOTATION_PATTERN.sub(_expand_relative_urls, html)
	return html


def quoted(url: str) -> str:
	return cstr(quote(encode(cstr(url)), safe=b"~@#$&()*!+=:;,.?/'"))


def quote_urls(html: str) -> str:
	def _quote_url(match):
		groups = list(match.groups())
		groups[2] = quoted(groups[2])
		return "".join(groups)

	return URLS_HTTP_TAG_PATTERN.sub(_quote_url, html)


def unique(seq: typing.Sequence["T"]) -> list["T"]:
	"""use this instead of list(set()) to preserve order of the original list.
	Thanks to Stackoverflow: http://stackoverflow.com/questions/480214/how-do-you-remove-duplicates-from-a-list-in-python-whilst-preserving-order"""

	seen = set()
	seen_add = seen.add
	return [x for x in seq if not (x in seen or seen_add(x))]


def strip(val: str, chars: str | None = None) -> str:
	# \ufeff is no-width-break, \u200b is no-width-space
	return (val or "").replace("\ufeff", "").replace("\u200b", "").strip(chars)


def get_string_between(start: str, string: str, end: str) -> str:
	if not string:
		return ""

	out = re.search(f"{start}(.*){end}", string)

	return out.group(1) if out else string


def to_markdown(html: str) -> str:
	from html.parser import HTMLParser

	from frappe.core.utils import html2text

	try:
		return html2text(html or "")
	except HTMLParser.HTMLParseError:
		pass


def md_to_html(markdown_text: str) -> Optional["UnicodeWithAttrs"]:
	from markdown2 import MarkdownError
	from markdown2 import markdown as _markdown

	extras = {
		"fenced-code-blocks": None,
		"tables": None,
		"header-ids": None,
		"toc": None,
		"highlightjs-lang": None,
		"html-classes": {"table": "table table-bordered", "img": "screenshot"},
	}

	try:
		return UnicodeWithAttrs(_markdown(markdown_text or "", extras=extras))
	except MarkdownError:
		pass


def markdown(markdown_text):
	return md_to_html(markdown_text)


def is_subset(list_a: list, list_b: list) -> bool:
	"""Returns whether list_a is a subset of list_b"""
	return len(list(set(list_a) & set(list_b))) == len(list_a)


def generate_hash(*args, **kwargs) -> str:
	return frappe.generate_hash(*args, **kwargs)


def dict_with_keys(dict, keys):
	"""Returns a new dict with a subset of keys"""
	out = {}
	for key in dict:
		if key in keys:
			out[key] = dict[key]
	return out


def guess_date_format(date_string: str) -> str:
	DATE_FORMATS = [
		r"%d/%b/%y",
		r"%d-%m-%Y",
		r"%m-%d-%Y",
		r"%Y-%m-%d",
		r"%d-%m-%y",
		r"%m-%d-%y",
		r"%y-%m-%d",
		r"%y-%b-%d",
		r"%d/%m/%Y",
		r"%m/%d/%Y",
		r"%Y/%m/%d",
		r"%d/%m/%y",
		r"%m/%d/%y",
		r"%y/%m/%d",
		r"%d.%m.%Y",
		r"%m.%d.%Y",
		r"%Y.%m.%d",
		r"%d.%m.%y",
		r"%m.%d.%y",
		r"%y.%m.%d",
		r"%d %b %Y",
		r"%d %B %Y",
	]

	TIME_FORMATS = [
		r"%H:%M:%S.%f",
		r"%H:%M:%S",
		r"%H:%M",
		r"%I:%M:%S.%f %p",
		r"%I:%M:%S %p",
		r"%I:%M %p",
	]

	def _get_date_format(date_str):
		for f in DATE_FORMATS:
			try:
				# if date is parsed without any exception
				# capture the date format
				datetime.datetime.strptime(date_str, f)
				return f
			except ValueError:
				pass

	def _get_time_format(time_str):
		for f in TIME_FORMATS:
			try:
				# if time is parsed without any exception
				# capture the time format
				datetime.datetime.strptime(time_str, f)
				return f
			except ValueError:
				pass

	date_format = None
	time_format = None
	date_string = date_string.strip()

	# check if date format can be guessed
	date_format = _get_date_format(date_string)
	if date_format:
		return date_format

	# check if time format can be guessed
	time_format = _get_time_format(date_string)
	if time_format:
		return time_format

	# date_string doesnt look like date, it can have a time part too
	# split the date string into date and time parts
	if " " in date_string:
		date_str, time_str = date_string.split(" ", 1)

		date_format = _get_date_format(date_str) or ""
		time_format = _get_time_format(time_str) or ""

		if date_format and time_format:
			return (date_format + " " + time_format).strip()


def validate_json_string(string: str) -> None:
	try:
		json.loads(string)
	except (TypeError, ValueError):
		raise frappe.ValidationError


class _UserInfo(typing.TypedDict):
	email: str
	image: str | None
	name: str


def get_user_info_for_avatar(user_id: str) -> _UserInfo:
	try:
		user = frappe.get_cached_doc("User", user_id)
		return {"email": user.email, "image": user.user_image, "name": user.full_name}

	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		return {"email": user_id, "image": "", "name": user_id}


def validate_python_code(
	string: str, fieldname: str | None = None, is_expression: bool = True
) -> None:
	"""Validate python code fields by using compile_command to ensure that expression is valid python.

	args:
	        fieldname: name of field being validated.
	        is_expression: true for validating simple single line python expression, else validated as script.
	"""

	if not string:
		return

	try:
		compile_command(string, symbol="eval" if is_expression else "exec")
	except SyntaxError as se:
		line_no = se.lineno - 1 or 0
		offset = se.offset - 1 or 0
		error_line = string if is_expression else string.split("\n")[line_no]
		msg = frappe._("{} Invalid python code on line {}").format(
			fieldname + ":" if fieldname else "", line_no + 1
		)
		msg += f"<br><pre>{error_line}</pre>"
		msg += f"<pre>{' ' * offset}^</pre>"

		frappe.throw(msg, title=frappe._("Syntax Error"))
	except Exception as e:
		frappe.msgprint(
			frappe._("{} Possibly invalid python code. <br>{}").format(fieldname + ": " or "", str(e)),
			indicator="orange",
		)


class UnicodeWithAttrs(str):
	def __init__(self, text):
		self.toc_html = text.toc_html
		self.metadata = text.metadata


def format_timedelta(o: datetime.timedelta) -> str:
	# mariadb allows a wide diff range - https://mariadb.com/kb/en/time/
	# but frappe doesnt - i think via babel : only allows 0..23 range for hour
	total_seconds = o.total_seconds()
	hours, remainder = divmod(total_seconds, 3600)
	minutes, seconds = divmod(remainder, 60)
	rounded_seconds = round(seconds, 6)
	int_seconds = int(seconds)

	if rounded_seconds == int_seconds:
		seconds = int_seconds
	else:
		seconds = rounded_seconds

	return f"{int(hours):01}:{int(minutes):02}:{seconds:02}"


def parse_timedelta(s: str) -> datetime.timedelta:
	# ref: https://stackoverflow.com/a/21074460/10309266
	if "day" in s:
		m = TIMEDELTA_DAY_PATTERN.match(s)
	else:
		m = TIMEDELTA_BASE_PATTERN.match(s)

	return datetime.timedelta(**{key: float(val) for key, val in m.groupdict().items()})


def get_job_name(key: str, doctype: str = None, doc_name: str = None) -> str:
	job_name = key
	if doctype:
		job_name += f"_{doctype}"
	if doc_name:
		job_name += f"_{doc_name}"
	return job_name


# This is used in test to count memory overhead of default imports.
def _get_rss_memory_usage():
	import psutil

	rss = psutil.Process().memory_info().rss // (1024 * 1024)
	return rss
