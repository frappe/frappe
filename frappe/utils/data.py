# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import base64
import calendar
import datetime
import hashlib
import json
import math
import operator
import re
import time
import typing
from code import compile_command
from collections import defaultdict
from enum import Enum
from functools import lru_cache
from typing import Any, Literal, Optional, TypeVar
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import orjson
from click import secho
from dateutil import parser
from dateutil.parser import ParserError
from dateutil.relativedelta import relativedelta

import frappe
from frappe.desk.utils import slug
from frappe.locale import get_date_format, get_first_day_of_the_week, get_number_format, get_time_format
from frappe.types.filter import Filters, FilterSignature, FilterTuple
from frappe.utils.deprecations import deprecated
from frappe.utils.number_format import NUMBER_FORMAT_MAP, NumberFormat

DateTimeLikeObject = str | datetime.date | datetime.datetime
NumericType = int | float
TimespanOptions = Literal[
	"last week",
	"last month",
	"last quarter",
	"last 6 months",
	"last year",
	"yesterday",
	"today",
	"tomorrow",
	"this week",
	"this month",
	"this quarter",
	"this year",
	"next week",
	"next month",
	"next quarter",
	"next 6 months",
	"next year",
]


if typing.TYPE_CHECKING:
	from collections.abc import Mapping

	from PIL.ImageFile import ImageFile as PILImageFile

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

# these options are necessary to use orjson with frappe
#
# OPT_PASSTHROUGH_DATETIME allows datetime objects to be passed through
# to the default function without conversion by orjson
# frappe converts datetime objects differently (__str__) from orjson (RFC 3339)
#
# OPT_NON_STR_KEYS slightly reduces performance of orjson, but allows for non-string keys in dicts
DEFAULT_ORJSON_OPTIONS = orjson.OPT_PASSTHROUGH_DATETIME | orjson.OPT_NON_STR_KEYS


class Weekday(Enum):
	Sunday = 0
	Monday = 1
	Tuesday = 2
	Wednesday = 3
	Thursday = 4
	Friday = 5
	Saturday = 6


def get_start_of_week_index() -> int:
	return Weekday[get_first_day_of_the_week()].value


def is_invalid_date_string(date_string: str) -> bool:
	"""Return True if the date string is invalid or None or empty."""
	# dateutil parser does not agree with dates like "0001-01-01" or "0000-00-00"
	return not isinstance(date_string, str) or (
		(not date_string) or (date_string or "").startswith(("0001-01-01", "0000-00-00"))
	)


def getdate(
	string_date: Optional["DateTimeLikeObject"] = None, parse_day_first: bool = False
) -> datetime.date | None:
	"""
	Convert string date (yyyy-mm-dd) to datetime.date object.
	If no input is provided, current date is returned.
	"""
	if not string_date:
		return get_datetime().date()
	elif isinstance(string_date, datetime.datetime):
		return string_date.date()

	elif isinstance(string_date, datetime.date):
		return string_date

	elif is_invalid_date_string(string_date):
		return None

	try:
		# PERF: Our DATE_FORMAT is same as ISO format.
		# fromisoformat is written in C so it's better than using strptime parser
		return datetime.date.fromisoformat(string_date)
	except ValueError:
		try:
			return parser.parse(string_date, dayfirst=parse_day_first).date()
		except ParserError:
			frappe.throw(
				frappe._("{} is not a valid date string.").format(frappe.bold(string_date)),
				title=frappe._("Invalid Date"),
			)


def get_datetime(
	datetime_str: Optional["DateTimeLikeObject"] | tuple | list = None,
) -> datetime.datetime | None:
	"""Return the below mentioned values based on the given `datetime_str`:

	* If `datetime_str` is None, returns datetime object of current datetime
	* If `datetime_str` is already a datetime object, returns the same
	* If `datetime_str` is a timedelta object, returns the same
	* If `datetime_str` is a list or tuple, returns a datetime object
	* If `datetime_str` is a date object, returns a datetime object
	* If `datetime_str` is a valid date string, returns a datetime object for the same
	* If `datetime_str` is an invalid date string, returns None
	"""

	if datetime_str is None:
		return now_datetime()

	elif isinstance(datetime_str, datetime.datetime | datetime.timedelta):
		return datetime_str

	elif isinstance(datetime_str, list | tuple):
		return datetime.datetime(datetime_str)

	elif isinstance(datetime_str, datetime.date):
		return datetime.datetime.combine(datetime_str, datetime.time())

	elif is_invalid_date_string(datetime_str):
		return None

	try:
		# PERF: Our DATETIME_FORMAT is same as ISO format.
		# fromisoformat is written in C so it's better than using strptime parser
		return datetime.datetime.fromisoformat(datetime_str)
	except ValueError:
		return parser.parse(datetime_str)


def get_timedelta(time: str | datetime.timedelta | None = None) -> datetime.timedelta | None:
	"""Return `datetime.timedelta` object from string value of a valid time format.

	Return None if `time` is not a valid format.

	Args:
	        time (str | datetime.timedelta): A valid time representation. This string is parsed
	        using `dateutil.parser.parse`. Examples of valid inputs are:
	        '0:0:0', '17:21:00', '2012-01-19 17:21:00'. Checkout
	        https://dateutil.readthedocs.io/en/stable/parser.html#dateutil.parser.parse

	Return:
	        datetime.timedelta: Timedelta object equivalent of the passed `time` string
	"""
	if isinstance(time, datetime.timedelta):
		return time

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
	"""Return a `datetime.timedelta` object from the given string or `datetime.time` object.
	If the given argument is not a string or a `datetime.time` object, it is returned as is.
	"""
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
) -> datetime.date: ...


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
) -> datetime.datetime: ...


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
) -> str: ...


def add_to_date(
	date: DateTimeLikeObject | None = None,
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
			date = get_datetime(date)
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


def add_days(date: DateTimeLikeObject, days: NumericType) -> DateTimeLikeObject:
	"""Return a new date after adding the given number of `days` to the given `date`."""
	return add_to_date(date, days=days)


def add_months(date: DateTimeLikeObject, months: NumericType) -> DateTimeLikeObject:
	"""Return a new date after adding the given number of `months` to the given `date`."""
	return add_to_date(date, months=months)


def add_years(date: DateTimeLikeObject, years: NumericType) -> DateTimeLikeObject:
	"""Return a new date after adding the given number of `years` to the given `date`."""
	return add_to_date(date, years=years)


def date_diff(string_ed_date: DateTimeLikeObject, string_st_date: DateTimeLikeObject) -> int:
	"""Return the difference between given two dates in days."""
	return days_diff(string_ed_date, string_st_date)


def days_diff(string_ed_date: DateTimeLikeObject, string_st_date: DateTimeLikeObject) -> int:
	"""Return the difference between given two dates in days."""
	return (getdate(string_ed_date) - getdate(string_st_date)).days


def month_diff(string_ed_date: DateTimeLikeObject, string_st_date: DateTimeLikeObject) -> int:
	"""Return the difference between given two dates in months."""
	ed_date = getdate(string_ed_date)
	st_date = getdate(string_st_date)
	return (ed_date.year - st_date.year) * 12 + ed_date.month - st_date.month + 1


def time_diff(string_ed_date: DateTimeLikeObject, string_st_date: DateTimeLikeObject) -> datetime.timedelta:
	"""Return the difference between given two dates as `datetime.timedelta` object."""
	return get_datetime(string_ed_date) - get_datetime(string_st_date)


def time_diff_in_seconds(string_ed_date: DateTimeLikeObject, string_st_date: DateTimeLikeObject) -> float:
	"""Return the difference between given two dates in seconds."""
	return time_diff(string_ed_date, string_st_date).total_seconds()


def time_diff_in_hours(string_ed_date: DateTimeLikeObject, string_st_date: DateTimeLikeObject) -> float:
	"""Return the difference between given two dates in hours."""
	return round(float(time_diff(string_ed_date, string_st_date).total_seconds()) / 3600, 6)


def now_datetime() -> datetime.datetime:
	"""Return the current datetime in system timezone."""
	return datetime.datetime.now(ZoneInfo(get_system_timezone())).replace(tzinfo=None)


def get_timestamp(date: Optional["DateTimeLikeObject"] = None) -> float:
	"""Return the Unix timestamp (seconds since Epoch) for the given `date`.
	If `date` is None, the current timestamp is returned.
	"""
	return time.mktime(getdate(date).timetuple())


def get_eta(from_time: DateTimeLikeObject, percent_complete) -> str:
	diff = time_diff(now_datetime(), from_time).total_seconds()
	return str(datetime.timedelta(seconds=(100 - percent_complete) / percent_complete * diff))


def get_system_timezone() -> str:
	"""Return the system timezone."""
	return frappe.get_system_settings("time_zone") or "Asia/Kolkata"  # Default to India ?!


def convert_utc_to_timezone(utc_timestamp: datetime.datetime, time_zone: str) -> datetime.datetime:
	if utc_timestamp.tzinfo is None:
		utc_timestamp = utc_timestamp.replace(tzinfo=ZoneInfo("UTC"))

	try:
		return utc_timestamp.astimezone(ZoneInfo(time_zone))
	except ZoneInfoNotFoundError:
		return utc_timestamp


def get_datetime_in_timezone(time_zone: str) -> datetime.datetime:
	"""Return the current datetime in the given timezone (e.g. 'Asia/Kolkata')."""
	utc_timestamp = datetime.datetime.now(datetime.timezone.utc)
	return convert_utc_to_timezone(utc_timestamp, time_zone)


def convert_utc_to_system_timezone(utc_timestamp: datetime.datetime) -> datetime.datetime:
	"""Return the given UTC `datetime` timestamp in system timezone."""
	time_zone = get_system_timezone()
	return convert_utc_to_timezone(utc_timestamp, time_zone)


def now() -> str:
	"""Return current datetime as `yyyy-mm-dd hh:mm:ss`."""
	if frappe.flags.current_date:
		return (
			getdate(frappe.flags.current_date).strftime(DATE_FORMAT)
			+ " "
			+ now_datetime().strftime(TIME_FORMAT)
		)
	else:
		return now_datetime().strftime(DATETIME_FORMAT)


def nowdate() -> str:
	"""Return current date as `yyyy-mm-dd`."""
	return now_datetime().strftime(DATE_FORMAT)


def today() -> str:
	"""Return today's date in `yyyy-mm-dd` format."""
	return nowdate()


def get_abbr(string: str, max_len: int = 2) -> str:
	"""Return the abbreviation of the given string.

	Examples:

	* "John Doe" => "JD"
	* "Jenny Jane Doe" => "JJ" (default, `max_len` = 2)
	* "Jenny Jane Doe" => "JJD" (`max_len` = 3)

	Return "?" if the given string is empty.
	"""
	abbr = ""
	for part in string.split(" "):
		if len(abbr) < max_len and part:
			abbr += part[0]

	return abbr or "?"


def nowtime() -> str:
	"""Return current time (system timezone) in `hh:mm:ss` format."""
	return now_datetime().strftime(TIME_FORMAT)


@typing.overload
def get_first_day(dt, d_years=0, d_months=0, as_str: Literal[False] = False) -> datetime.date: ...


@typing.overload
def get_first_day(dt, d_years=0, d_months=0, as_str: Literal[True] = False) -> str: ...


# TODO: first arg
def get_first_day(dt, d_years: int = 0, d_months: int = 0, as_str: bool = False) -> str | datetime.date:
	"""Return the first day of the month for the date specified by date object.

	Also, add `d_years` and `d_months` if specified.
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
def get_quarter_start(
	dt: DateTimeLikeObject | None = None, as_str: Literal[False] = False
) -> datetime.date: ...


@typing.overload
def get_quarter_start(dt: DateTimeLikeObject | None = None, as_str: Literal[True] = False) -> str: ...


def get_quarter_start(dt: DateTimeLikeObject | None = None, as_str: bool = False) -> str | datetime.date:
	"""Return the start date of the quarter for the given datetime like object (`dt`).

	If `dt` is None, the current quarter start date is returned.
	"""
	date = getdate(dt)
	quarter = (date.month - 1) // 3 + 1
	first_date_of_quarter = datetime.date(date.year, ((quarter - 1) * 3) + 1, 1)
	return first_date_of_quarter.strftime(DATE_FORMAT) if as_str else first_date_of_quarter


@typing.overload
def get_first_day_of_week(dt: DateTimeLikeObject, as_str: Literal[False] = False) -> datetime.date: ...


@typing.overload
def get_first_day_of_week(dt: DateTimeLikeObject, as_str: Literal[True] = False) -> str: ...


def get_first_day_of_week(dt: DateTimeLikeObject, as_str=False) -> datetime.date | str:
	"""Return the first day of the week (as per System Settings or Sunday by default) for the given datetime like object (`dt`).

	If `as_str` is True, the first day of the week is returned as a string in `yyyy-mm-dd` format.
	"""
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


@typing.overload
def get_year_start(dt: DateTimeLikeObject, as_str: Literal[False] = False) -> datetime.date: ...


@typing.overload
def get_year_start(dt: DateTimeLikeObject, as_str: Literal[True] = False) -> str: ...


def get_year_start(dt: DateTimeLikeObject, as_str=False) -> str | datetime.date:
	"""Return the start date of the year for the given date (`dt`)."""
	dt = getdate(dt)
	date = datetime.date(dt.year, 1, 1)
	return date.strftime(DATE_FORMAT) if as_str else date


@typing.overload
def get_last_day_of_week(dt: DateTimeLikeObject, as_str: Literal[False] = False) -> datetime.date: ...


@typing.overload
def get_last_day_of_week(dt: DateTimeLikeObject, as_str: Literal[True] = False) -> str: ...


def get_last_day_of_week(dt: DateTimeLikeObject, as_str=False) -> datetime.date | str:
	"""Return the last day of the week (first day is taken from System Settings or Sunday by default) for the given datetime like object (`dt`).

	If `as_str` is True, the last day of the week is returned as a string in `yyyy-mm-dd` format.
	"""
	dt = get_first_day_of_week(dt)
	date = dt + datetime.timedelta(days=6)
	return date.strftime(DATE_FORMAT) if as_str else date


def get_last_day(dt):
	"""Return last day of the month using:

	`get_first_day(dt, 0, 1) + datetime.timedelta(-1)`
	"""
	return get_first_day(dt, 0, 1) + datetime.timedelta(-1)


def is_last_day_of_the_month(dt):
	last_day_of_the_month = get_last_day(dt)

	return getdate(dt) == getdate(last_day_of_the_month)


@typing.overload
def get_quarter_ending(
	dt: DateTimeLikeObject | None = None, as_str: Literal[False] = False
) -> datetime.date: ...


@typing.overload
def get_quarter_ending(dt: DateTimeLikeObject | None = None, as_str: Literal[True] = False) -> str: ...


def get_quarter_ending(date: DateTimeLikeObject | None = None, as_str=False) -> str | datetime.date:
	"""Return the end date of the quarter for the given datetime like object (`date`).

	If `date` is None, the current quarter end date is returned.
	If `as_str` is True, the end date of the quarter is returned as a string in `yyyy-mm-dd` format.
	"""
	date = getdate(date)

	# find the earliest quarter ending date that is after
	# the given date
	for month in (3, 6, 9, 12):
		quarter_end_month = getdate(f"{date.year}-{month}-01")
		quarter_end_date = getdate(get_last_day(quarter_end_month))
		if date <= quarter_end_date:
			date = quarter_end_date
			break

	return date.strftime(DATE_FORMAT) if as_str else date


@typing.overload
def get_year_ending(
	dt: DateTimeLikeObject | None = None, as_str: Literal[False] = False
) -> datetime.date: ...


@typing.overload
def get_year_ending(dt: DateTimeLikeObject | None = None, as_str: Literal[True] = False) -> str: ...


def get_year_ending(date: DateTimeLikeObject | None = None, as_str=False) -> datetime.date | str:
	"""Return the end date of the year for the given datetime like object (`date`).

	If `date` is None, the current year end date is returned.
	If `as_str` is True, the end date of the year is returned as a string in `yyyy-mm-dd` format.
	"""
	date = getdate(date)
	next_year_start = datetime.date(date.year + 1, 1, 1)
	year_ending = add_to_date(next_year_start, days=-1)
	return year_ending.strftime(DATE_FORMAT) if as_str else year_ending


def get_time(
	time_str: str | datetime.datetime | datetime.time | datetime.timedelta,
) -> datetime.time:
	"""Return a `datetime.time` object for the given `time_str`.

	If the given argument is already a `datetime.time` object, it is returned as is."""

	if isinstance(time_str, datetime.datetime):
		return time_str.time()
	elif isinstance(time_str, datetime.time):
		return time_str
	elif isinstance(time_str, datetime.timedelta):
		return (datetime.datetime.min + time_str).time()

	try:
		# PERF: Our DATE_FORMAT is same as ISO format.
		return datetime.time.fromisoformat(time_str)
	except ValueError:
		try:
			return parser.parse(time_str).time()
		except ParserError as e:
			if "day" in e.args[1] or "hour must be in" in e.args[0]:
				return (datetime.datetime.min + parse_timedelta(time_str)).time()
			raise e


def get_datetime_str(datetime_obj: DateTimeLikeObject) -> str:
	"""Return the given datetime like object (datetime.date, datetime.datetime, string) as a string in `yyyy-mm-dd hh:mm:ss` format."""
	if isinstance(datetime_obj, str):
		datetime_obj = get_datetime(datetime_obj)
	return datetime_obj.strftime(DATETIME_FORMAT)


def get_date_str(date_obj: DateTimeLikeObject) -> str:
	"""Return the given datetime like object (datetime.date, datetime.datetime, string) as a string in `yyyy-mm-dd` format."""
	if isinstance(date_obj, str):
		date_obj = get_datetime(date_obj)
	return date_obj.strftime(DATE_FORMAT)


def get_time_str(timedelta_obj: datetime.timedelta | str) -> str:
	"""Return the given timedelta object as a string in `hh:mm:ss` format."""
	if isinstance(timedelta_obj, str):
		timedelta_obj = to_timedelta(timedelta_obj)

	hours, remainder = divmod(timedelta_obj.seconds, 3600)
	minutes, seconds = divmod(remainder, 60)
	return f"{hours}:{minutes}:{seconds}"


def get_user_date_format() -> str:
	"""Get the current user date format. The result will be cached."""
	if getattr(frappe.local, "user_date_format", None) is None:
		frappe.local.user_date_format = get_date_format()

	return frappe.local.user_date_format


get_user_format = get_user_date_format  # for backwards compatibility


def get_user_time_format() -> str:
	"""Get the current user time format. The result will be cached."""
	if getattr(frappe.local, "user_time_format", None) is None:
		frappe.local.user_time_format = get_time_format()

	return frappe.local.user_time_format


def format_date(string_date=None, format_string: str | None = None, parse_day_first: bool = False) -> str:
	"""Convert the given string date to :data:`user_date_format`.

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
	except (UnknownLocaleError, ValueError):
		format_string = format_string.replace("MM", "%m").replace("dd", "%d").replace("yyyy", "%Y")
		formatted_date = date.strftime(format_string)
	return formatted_date


formatdate = format_date  # For backwards compatibility


def format_time(time_string=None, format_string: str | None = None) -> str:
	"""Convert the given string time to :data:`user_time_format`.

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
	except (UnknownLocaleError, ValueError):
		formatted_time = time_.strftime("%H:%M:%S")
	return formatted_time


def format_datetime(datetime_string: DateTimeLikeObject, format_string: str | None = None) -> str:
	"""Convert the given string time to :data:`user_datetime_format`
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
	except (UnknownLocaleError, ValueError):
		formatted_datetime = datetime.strftime("%Y-%m-%d %H:%M:%S")
	return formatted_datetime


def format_duration(seconds, hide_days=False):
	"""Convert the given duration value in float(seconds) to duration format.

	example: convert 12885 to '3h 34m 45s' where 12885 = seconds in float
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
	"""Convert the given duration formatted value to duration value in seconds.

	example: convert '3h 34m 45s' to 12885 (value in seconds)
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
			frappe._("Value {0} must be in the valid duration format: d h m s").format(frappe.bold(duration))
		)


def get_weekdays() -> list[str]:
	"""Return a list of weekday names.

	Return value: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
	"""
	return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get_weekday(datetime: DateTimeLikeObject | None = None) -> str:
	"""Return the weekday name (e.g. 'Sunday') for the given datetime like object (datetime.date, datetime.datetime, string).

	If `datetime` argument is not provided, the current weekday name is returned.
	"""
	if not datetime:
		datetime = now_datetime()

	if isinstance(datetime, str):
		datetime = get_datetime(datetime)

	weekdays = get_weekdays()
	return weekdays[datetime.weekday()]


def get_month(datetime: DateTimeLikeObject | None = None) -> str:
	"""Return the month name (e.g. 'January') for the given datetime like object (datetime.date, datetime.datetime, string).

	If `datetime` argument is not provided, the current month name is returned.
	"""
	if not datetime:
		datetime = now_datetime()

	if isinstance(datetime, str):
		datetime = get_datetime(datetime)

	return calendar.month_name[datetime.month]


def get_timespan_date_range(
	timespan: TimespanOptions,
) -> tuple[datetime.datetime, datetime.datetime] | None:
	"""Return the date range (start_date, end_date) tuple for the given timespan."""
	today = getdate()

	match timespan:
		case "last 7 days":
			return (add_to_date(today, days=-7), today)
		case "last 14 days":
			return (add_to_date(today, days=-14), today)
		case "last 30 days":
			return (add_to_date(today, days=-30), today)
		case "last 90 days":
			return (add_to_date(today, days=-90), today)
		case "last week":
			return (
				get_first_day_of_week(add_to_date(today, days=-7)),
				get_last_day_of_week(add_to_date(today, days=-7)),
			)
		case "last month":
			return (
				get_first_day(add_to_date(today, months=-1)),
				get_last_day(add_to_date(today, months=-1)),
			)
		case "last quarter":
			return (
				get_quarter_start(add_to_date(today, months=-3)),
				get_quarter_ending(add_to_date(today, months=-3)),
			)
		case "last 6 months":
			return (
				get_quarter_start(add_to_date(today, months=-6)),
				get_quarter_ending(add_to_date(today, months=-3)),
			)
		case "last year":
			return (
				get_year_start(add_to_date(today, years=-1)),
				get_year_ending(add_to_date(today, years=-1)),
			)

		case "yesterday":
			return (add_to_date(today, days=-1),) * 2
		case "today":
			return (today, today)
		case "tomorrow":
			return (add_to_date(today, days=1),) * 2
		case "this week":
			return (get_first_day_of_week(today), get_last_day_of_week(today))
		case "this month":
			return (get_first_day(today), get_last_day(today))
		case "this quarter":
			return (get_quarter_start(today), get_quarter_ending(today))
		case "this year":
			return (get_year_start(today), get_year_ending(today))
		case "next 7 days":
			return (
				today,
				add_to_date(today, days=7),
			)
		case "next 14 days":
			return (
				today,
				add_to_date(today, days=14),
			)
		case "next 30 days":
			return (
				today,
				add_to_date(today, days=30),
			)
		case "next week":
			return (
				get_first_day_of_week(add_to_date(today, days=7)),
				get_last_day_of_week(add_to_date(today, days=7)),
			)
		case "next month":
			return (
				get_first_day(add_to_date(today, months=1)),
				get_last_day(add_to_date(today, months=1)),
			)
		case "next quarter":
			return (
				get_quarter_start(add_to_date(today, months=3)),
				get_quarter_ending(add_to_date(today, months=3)),
			)
		case "next 6 months":
			return (
				get_quarter_start(add_to_date(today, months=3)),
				get_quarter_ending(add_to_date(today, months=6)),
			)
		case "next year":
			return (
				get_year_start(add_to_date(today, years=1)),
				get_year_ending(add_to_date(today, years=1)),
			)
		case _:
			return


def global_date_format(date: DateTimeLikeObject, format="long") -> str:
	"""Return localized date in the form of 'January 1, 2012'."""
	import babel.dates

	date = getdate(date)
	return babel.dates.format_date(date, locale=(frappe.local.lang or "en").replace("-", "_"), format=format)


def has_common(l1: typing.Hashable, l2: typing.Hashable) -> bool:
	"""Return truthy value if there are common elements in lists l1 and l2."""
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
def flt(s: NumericType | str, precision: Literal[0]) -> int: ...


@typing.overload
def flt(s: NumericType | str, precision: int | None = None) -> float: ...


@typing.overload
def flt(s: None) -> Literal[0.0]: ...


def flt(
	s: NumericType | str | None, precision: int | None = None, rounding_method: str | None = None
) -> float:
	"""Convert to float (ignoring commas in string).

	:param s: Number in string or other numeric format.
	:param precision: optional argument to specify precision for rounding.
	:returns: Converted number in python float type.

	Return 0 if input can not be converted to float.

	Examples:

	>>> flt("43.5", precision=0)
	44
	>>> flt("42.5", precision=0)
	42
	>>> flt("10,500.5666", precision=2)
	10500.57
	>>> flt("a")
	0.0
	>>> flt(None)
	0.0
	"""

	if s is None:
		return 0.0

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


def cint(s: NumericType | str | None, default: int = 0) -> int:
	"""Convert to integer.

	:param s: Number in string or other numeric format.
	:returns: Converted number in python integer type.

	Return default if input cannot be converted to integer.

	Examples:
	>>> cint("100")
	100
	>>> cint("a")
	0
	>>> cint(None)
	0

	"""
	if s is None:
		return default

	try:
		return int(s)
	except Exception:
		try:
			return int(float(s))
		except Exception:
			return default


def floor(s: NumericType | str) -> int:
	"""Return a number representing the largest integer less than or equal to the specified number."""
	try:
		num = cint(math.floor(flt(s)))
	except Exception:
		num = 0
	return num


def ceil(s: NumericType | str) -> int:
	"""Return the smallest integer greater than or equal to the given number."""
	try:
		num = cint(math.ceil(flt(s)))
	except Exception:
		num = 0
	return num


def cstr(s, encoding="utf-8") -> str:
	"""Convert the given argument to string."""
	return frappe.as_unicode(s, encoding)


def sbool(x: str | Any) -> bool | str | Any:
	"""Convert str object to Boolean if possible.

	Example:
	        "true" becomes True
	        "1" becomes True
	        "{}" remains "{}"

	Args:
	        x (str): String to be converted to Bool

	Return Boolean or x.
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

	if rounding_method == "Banker's Rounding":
		return _bankers_rounding(num, precision)
	elif rounding_method == "Banker's Rounding (legacy)":
		return _bankers_rounding_legacy(num, precision)
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
	"""Return the remainder of the division of `numerator` by `denominator`."""
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
	"""Convert to simple datatypes from SQL query results."""
	if isinstance(v, datetime.date | datetime.datetime):
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
	"""Convert to string with commas for thousands, millions etc."""
	number_format = NumberFormat.from_string(format) if format else get_number_format()

	if precision is None:
		precision = cint(frappe.db.get_default("currency_precision")) or None

	if precision is None:
		precision = number_format.precision

	# 40,000 -> 40,000.00
	# 40,000.00000 -> 40,000.00
	# 40,000.23000 -> 40,000.23

	if isinstance(amount, str):
		amount = flt(amount, precision)

	if amount is None:
		amount = 0

	if number_format.decimal_separator:
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
					precision = number_format.precision
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

		val = 2 if number_format.string == "#,##,###.##" else 3

		while len(amount) > val:
			parts.append(amount[-val:])
			amount = amount[:-val]

	parts.append(amount)

	parts.reverse()

	amount = number_format.thousands_separator.join(parts) + (
		((precision and number_format.decimal_separator) and (number_format.decimal_separator + decimals))
		or ""
	)
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


from frappe.deprecation_dumpster import get_number_format_info


def __getattr__(name):
	if name == "number_format_info":
		from frappe.deprecation_dumpster import deprecation_warning
		from frappe.utils.number_format import NUMBER_FORMAT_MAP

		deprecation_warning(
			"unkown",
			"v16",
			"use frappe.utils.number_format.NUMBER_FORMAT_MAP instead of frappe.utils.data.number_format_info",
		)
	else:
		try:
			globals()[name]
		except KeyError:
			raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


#
# convert currency to words
#
def money_in_words(
	number: str | float | int,
	main_currency: str | None = None,
	fraction_currency: str | None = None,
):
	"""Return string in words with currency and fraction currency."""
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

	number_format = get_number_format()

	fraction_units = frappe.db.get_value("Currency", main_currency, "fraction_units", cache=True)
	fraction_length = math.ceil(math.log10(fraction_units)) or number_format.precision

	n = f"%.{fraction_length}f" % number

	numbers = n.split(".")
	main, fraction = numbers if len(numbers) > 1 else [n, "00"]

	if len(fraction) < fraction_length:
		zeros = "0" * (fraction_length - len(fraction))
		fraction += zeros

	in_million = True
	if number_format.string == "#,##,###.##":
		in_million = False

	def fraction_in_words() -> str:
		return in_words(float(f"0.{fraction}") * fraction_units, in_million).title()

	# 0.00
	if main == "0" and fraction in ["0", "00", "000"]:
		out = _(main_currency, context="Currency") + " " + _("Zero")
	elif main == "0":
		out = f"{fraction_in_words()} {fraction_currency}"
	else:
		out = _(main_currency, context="Currency") + " " + in_words(main, in_million).title()
		if cint(fraction):
			out = out + " " + _("and") + " " + fraction_in_words() + " " + fraction_currency

	return _("{0} only.", context="Money in words").format(out)


#
# convert number to words
#
def in_words(integer: int, in_million=True) -> str:
	"""Return string in words for the given integer."""
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
	"""Return True if the given `text` contains any HTML tags."""
	if not isinstance(text, str):
		return False
	return HTML_TAG_PATTERN.search(text)


def is_image(filepath: str) -> bool:
	"""Return True if the given `filepath` points to an image file."""
	from mimetypes import guess_type

	# filepath can be https://example.com/bed.jpg?v=129
	filepath = (filepath or "").split("?", 1)[0]
	return (guess_type(filepath)[0] or "").startswith("image/")


def get_thumbnail_base64_for_image(src: str) -> dict[str, str] | None:
	"""Return the base64 encoded string for the thumbnail of the given image source path.

	Example return value:

	{
	        "base64": "data:image/ext;base64,...",
	        "width": 50,
	        "height": 50
	}
	"""
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


def image_to_base64(image: "PILImageFile", extn: str) -> bytes:
	"""Return the base64 encoded string for the given PIL `ImageFile`."""
	from io import BytesIO

	buffered = BytesIO()
	if extn.lower() in ("jpg", "jpe"):
		extn = "JPEG"
	image.save(buffered, extn)
	return base64.b64encode(buffered.getvalue())


def pdf_to_base64(filename: str) -> bytes | None:
	"""Return the base64 encoded string for the given PDF file.

	Return None if the file is not found or is not a PDF file."""
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
	"""Remove anything enclosed in and including <>."""
	return _striptags_re.sub("", text)


def escape_html(text: str) -> str:
	"""Return the given text with HTML special characters escaped.

	e.g. '<h1>Hello</h1>' -> '&lt;h1&gt;Hello&lt;/h1&gt;'
	"""
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


def pretty_date(iso_datetime: datetime.datetime | str, mini=False) -> str:
	"""Return a localized string representation of the delta to the current system time.

	For example, "1 hour ago", "2 days ago", "in 5 seconds", etc.
	"""
	if not iso_datetime:
		return ""

	from babel.dates import format_timedelta

	if isinstance(iso_datetime, str):
		iso_datetime = get_datetime(iso_datetime)
	now_dt = now_datetime()
	locale = frappe.local.lang.replace("-", "_") if frappe.local.lang else None
	return format_timedelta(
		iso_datetime - now_dt,
		add_direction=not mini,
		locale=locale,
		format="long" if not mini else "narrow",
	)


def comma_or(some_list: list | tuple, add_quotes=True) -> str:
	"""Return the given list or tuple as a comma separated string with the last item joined by 'or'.
	e.g. ['a', 'b', 'c'] -> 'a, b or c'

	If `add_quotes` is True, each item in the list will be wrapped in single quotes.
	e.g. ['a', 'b', 'c'] -> "'a', 'b' or 'c'"
	"""
	return comma_sep(some_list, frappe._("{0} or {1}"), add_quotes)


def comma_and(some_list: list | tuple, add_quotes=True) -> str:
	"""Return the given list or tuple as a comma separated string with the last item joined by 'and'.
	e.g. ['a', 'b', 'c'] -> 'a, b and c'

	If `add_quotes` is True, each item in the list will be wrapped in single quotes.
	e.g. ['a', 'b', 'c'] -> "'a', 'b' and 'c'"
	"""
	return comma_sep(some_list, frappe._("{0} and {1}"), add_quotes)


def comma_sep(some_list: list | tuple, pattern: str, add_quotes=True) -> str:
	"""Return the given list or tuple as a comma separated string, with the last item joined by the given string format pattern.

	If `add_quotes` is True, each item in the list will be wrapped in single quotes.

	e.g. if `some_list` is ['a', 'b', 'c'] and `pattern` is '{0} or {1}', the output will be 'a, b or c'
	"""
	if isinstance(some_list, list | tuple):
		# list(some_list) is done to preserve the existing list
		some_list = [str(s) for s in list(some_list)]
		if not some_list:
			return ""
		elif len(some_list) == 1:
			return some_list[0]
		else:
			some_list = (
				["'{}'".format(s) for s in some_list] if add_quotes else ["{}".format(s) for s in some_list]
			)
			return pattern.format(", ".join(frappe._(s) for s in some_list[:-1]), some_list[-1])
	else:
		return some_list


def new_line_sep(some_list: list | tuple) -> str:
	"""Return the given list or tuple as a new line separated string.

	e.g. ['', 'Paid', 'Unpaid'] -> '\n Paid\n Unpaid'
	"""
	if isinstance(some_list, list | tuple):
		# list(some_list) is done to preserve the existing list
		some_list = [str(s) for s in list(some_list)]
		if not some_list:
			return ""
		elif len(some_list) == 1:
			return some_list[0]
		else:
			some_list = ["{}".format(s) for s in some_list]
			return format("\n ".join(some_list))
	else:
		return some_list


def filter_strip_join(some_list: list[str], sep: str) -> list[str]:
	"""given a list, filter None values, strip spaces and join"""
	return (cstr(sep)).join(cstr(a).strip() for a in filter(None, some_list))


def get_url(
	uri: str | None = None,
	full_address: bool = False,
	allow_header_override: bool = True,
) -> str:
	"""Get app url from request."""
	host_name = frappe.local.conf.host_name or frappe.local.conf.hostname

	if uri and (uri.startswith("http://") or uri.startswith("https://")):
		return uri

	if not host_name:
		request_host_name = get_host_name_from_request()

		if request_host_name and allow_header_override:
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
				host_name = "http://127.0.0.1"

	if host_name and not host_name.startswith("http://") and not host_name.startswith("https://"):
		host_name = "http://" + host_name

	if not uri and full_address:
		uri = frappe.get_request_header("REQUEST_URI", "")

	port = frappe.conf.http_port
	if not port and frappe.conf.developer_mode:
		port = frappe.conf.webserver_port

	if (
		# XXX: This config is used as proxy for "is production mode enabled?"
		not frappe.conf.restart_supervisor_on_update
		and not frappe.conf.restart_systemd_on_update
		and host_name
		and not url_contains_port(host_name)
		and port
	):
		host_name = host_name + ":" + str(port)

	return urljoin(host_name, uri) if uri else host_name


def get_host_name_from_request() -> str:
	"""Return the hostname (`request.host`) from the request headers."""
	if hasattr(frappe.local, "request") and frappe.local.request and frappe.local.request.host:
		protocol = "https://" if "https" == frappe.get_request_header("X-Forwarded-Proto", "") else "http://"
		return protocol + frappe.local.request.host


def url_contains_port(url: str) -> bool:
	"""Return True if the given url contains a port number.

	e.g. 'http://localhost:8000' -> True, 'http://localhost' -> False.
	"""
	parts = url.split(":")
	return len(parts) > 2


def get_host_name() -> str:
	"""Return the hostname of the current site.

	e.g. If site is 'https://cloud.frappe.io', returns 'cloud.frappe.io'.
	"""
	return get_url().rsplit("//", 1)[-1]


def get_link_to_form(doctype: str, name: str | None = None, label: str | None = None) -> str:
	"""Return the HTML link to the given document's form view.

	e.g. get_link_to_form("Sales Invoice", "INV-0001", "Link Label") returns:
	    '<a href="https://frappe.io/app/sales-invoice/INV-0001">Link Label</a>'.
	"""
	from frappe import _

	if not label:
		label = name or _(doctype)

	return f"""<a href="{get_url_to_form(doctype, name)}">{label}</a>"""


def get_link_to_report(
	name: str,
	label: str | None = None,
	report_type: str | None = None,
	doctype: str | None = None,
	filters: dict | None = None,
) -> str:
	"""Return the HTML link to the given report.

	e.g. get_link_to_report("Revenue Report", "Link Label") returns:
	        '<a href="https://frappe.io/app/query-report/Revenue%20Report">Link Label</a>'.
	"""
	if not label:
		label = name

	if filters:
		conditions = []
		for k, v in filters.items():
			if isinstance(v, list):
				conditions.extend(
					str(k) + "=" + '["' + str(value[0] + '"' + "," + '"' + str(value[1]) + '"]')
					for value in v
				)
			else:
				conditions.append(str(k) + "=" + quote(str(v)))

		filters = "&".join(conditions)

		return """<a href='{}'>{}</a>""".format(
			get_url_to_report_with_filters(name, filters, report_type, doctype), label
		)
	else:
		return f"""<a href='{get_url_to_report(name, report_type, doctype)}'>{label}</a>"""


def get_absolute_url(doctype: str, name: str) -> str:
	"""Return the absolute route for the form view of the given document in the desk.

	e.g. when doctype="Sales Invoice" and name="INV-00001", returns '/app/sales-invoice/INV-00001'
	"""
	return f"/app/{quoted(slug(doctype))}/{quoted(name)}"


def get_url_to_form(doctype: str, name: str | None = None) -> str:
	"""Return the absolute URL for the form view of the given document in the desk.

	e.g. when doctype="Sales Invoice" and your site URL is "https://frappe.io",
	         returns 'https://frappe.io/app/sales-invoice/INV-00001'
	"""
	if not name:
		uri = f"/app/{quoted(slug(doctype))}"
	else:
		uri = f"/app/{quoted(slug(doctype))}/{quoted(name)}"

	return get_url(uri=uri)


def get_url_to_list(doctype: str) -> str:
	"""Return the absolute URL for the list view of the given document in the desk.

	e.g. when doctype="Sales Invoice" and your site URL is "https://frappe.io",
	         returns 'https://frappe.io/app/sales-invoice'
	"""
	return get_url(uri=f"/app/{quoted(slug(doctype))}")


def get_url_to_report(name, report_type: str | None = None, doctype: str | None = None) -> str:
	"""Return the absolute URL for the report in the desk.

	e.g. when name="Sales Register" and your site URL is "https://frappe.io",
	         returns 'https://frappe.io/app/query-report/Sales%20Register'

	You can optionally pass `report_type` and `doctype` to get the URL for a Report Builder report.

	get_url_to_report("Revenue", "Report Builder", "Sales Invoice") -> 'https://frappe.io/app/sales-invoice/view/report/Revenue'
	"""
	if report_type == "Report Builder":
		return get_url(uri=f"/app/{quoted(slug(doctype))}/view/report/{quoted(name)}")
	else:
		return get_url(uri=f"/app/query-report/{quoted(name)}")


def get_url_to_report_with_filters(name, filters, report_type=None, doctype=None):
	"""Return the absolute URL for the report in the desk with filters."""
	if report_type == "Report Builder":
		return get_url(uri=f"/app/{quoted(slug(doctype))}/view/report?{filters}")

	return get_url(uri=f"/app/query-report/{quoted(name)}?{filters}")


def sql_like(value: str, pattern: str) -> bool:
	if not isinstance(pattern, str) and isinstance(value, str):
		return False
	if pattern.startswith("%") and pattern.endswith("%"):
		return pattern.strip("%") in value
	elif pattern.startswith("%"):
		return value.endswith(pattern.lstrip("%"))
	elif pattern.endswith("%"):
		return value.startswith(pattern.rstrip("%"))
	else:
		# assume default as wrapped in '%'
		return pattern in value


def filter_operator_is(value: str, pattern: str) -> bool:
	"""Operator `is` can have two values: 'set' or 'not set'."""
	pattern = pattern.lower()

	def is_set():
		if value is None:
			return False
		elif isinstance(value, str) and not value:
			return False
		return True

	if pattern == "set":
		return is_set()
	elif pattern == "not set":
		return not is_set()
	else:
		frappe.throw(frappe._(f"Invalid argument for operator 'IS': {pattern}"))


def filter_operator_timespan(value: str, pattern: str) -> bool:
	if not value:
		return False

	date_range = get_timespan_date_range(pattern)
	return date_range[0] <= getdate(value) <= date_range[1]


operator_map = {
	# startswith
	"^": lambda a, b: (a or "").startswith(b),
	# in or not in a list
	"in": lambda a, b: operator.contains(b, a),
	"not in": lambda a, b: not operator.contains(b, a),
	# comparison operators
	"=": operator.eq,
	"!=": operator.ne,
	">": operator.gt,
	"<": operator.lt,
	">=": operator.ge,
	"<=": operator.le,
	"not None": lambda a, b: a is not None,
	"None": lambda a, b: a is None,
	"like": sql_like,
	"not like": lambda a, b: not sql_like(a, b),
	"is": filter_operator_is,
	"Timespan": filter_operator_timespan,
}


def evaluate_filters(doc: "Mapping", filters: FilterSignature):
	"""Return True if doc matches filters."""
	if not isinstance(filters, Filters):
		filters = Filters(filters, doctype=doc.get("doctype"))
	for d in filters:
		f = get_filter(None, d)
		if not compare(doc.get(f.fieldname), f.operator, f.value, f.fieldtype):
			return False

	return True


def compare(val1: Any, condition: str, val2: Any, fieldtype: str | None = None):
	if fieldtype:
		val1 = cast(fieldtype, val1)
		if condition != "Timespan":
			val2 = cast(fieldtype, val2)
	if condition in operator_map:
		return operator_map[condition](val1, val2)

	return False


def get_filter(doctype: str, filters: FilterSignature, filters_config=None) -> "frappe._dict":
	"""Return a `_dict` like:

	{
	        "doctype": ...
	        "fieldname": ...
	        "operator": ...
	        "value": ...
	        "fieldtype": ...
	}
	"""
	from frappe.database.utils import NestedSetHierarchy
	from frappe.model import child_table_fields, default_fields, optional_fields

	ft: FilterTuple
	if isinstance(filters, FilterTuple):
		ft = filters
	elif not isinstance(filters, Filters):
		ft = Filters(filters, doctype=doctype)[0]
	else:
		ft = filters[0]

	f = frappe._dict(doctype=ft[0], fieldname=ft[1], operator=ft[2], value=ft[3])

	f.fieldname = sanitize_column(f.fieldname)

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
		"timespan",
		"previous",
		"next",
		*NestedSetHierarchy,
	)

	if filters_config:
		additional_operators = [key.lower() for key in filters_config]
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
		df = frappe.get_meta(f.doctype).get_field(f.fieldname) if f.doctype else None
	except frappe.exceptions.DoesNotExistError:
		df = None

	f.fieldtype = df.fieldtype if df else None

	return f


def make_filter_tuple(doctype, key, value):
	"""return a filter tuple like [doctype, key, operator, value]"""
	if isinstance(value, list | tuple):
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


def sanitize_column(column_name: str) -> str:
	return _sanitize_column(column_name, (frappe.db and frappe.db.db_type) or None)


@lru_cache(maxsize=1024)
def _sanitize_column(column_name: str, db_type: str) -> str:
	import sqlparse

	from frappe import _

	column_name = sqlparse.format(column_name, strip_comments=True, keyword_case="lower")
	if db_type == "mariadb":
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

	regex = re.compile("^.*[,'();\n].*")
	if "ifnull" in column_name:
		if regex.match(column_name):
			# to avoid and, or
			if any(f" {keyword} " in column_name.split() for keyword in blacklisted_keywords):
				_raise_exception()

			# to avoid select, delete, drop, update and case
			elif any(keyword in column_name.split() for keyword in blacklisted_keywords):
				_raise_exception()

			elif any(
				re.search(rf"\b{keyword}\b", column_name, re.IGNORECASE) for keyword in blacklisted_keywords
			):
				_raise_exception()

	elif regex.match(column_name):
		_raise_exception()

	return column_name


def scrub_urls(html: str) -> str:
	"""Expand relative urls in the given `html`.

	e.g. If HTML is '<a href="/files/abc.jpeg">View Image</a>' and site URL is 'https://frappe.io',
	        returns '<a href="https://frappe.io/files/abc.jpeg">View Image</a>'.
	"""
	return expand_relative_urls(html)


def expand_relative_urls(html: str) -> str:
	"""Expand relative urls in the given `html`.

	e.g. If HTML is '<a href="/files/abc.jpeg">View Image</a>' and site URL is 'https://frappe.io',
	        returns '<a href="https://frappe.io/files/abc.jpeg">View Image</a>'.
	"""
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
	"""Return the given `url` quoted.

	e.g. 'https://frappe.io/files/my Image file.jpeg' -> 'https://frappe.io/files/my%20Image%20file.jpeg'
	"""
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
	"""Strip the given characters from the given string.

	e.g. strip(',hello,bye,', ',') -> 'hello,bye'
	"""
	# \ufeff is no-width-break, \u200b is no-width-space
	return (val or "").replace("\ufeff", "").replace("\u200b", "").strip(chars)


def get_string_between(start: str, string: str, end: str) -> str:
	if not string:
		return ""

	out = re.search(f"{start}(.*){end}", string)

	return out.group(1) if out else string


def to_markdown(html: str) -> str:
	"""Convert the given HTML to markdown and returns it."""
	from html.parser import HTMLParser

	from frappe.core.utils import html2text

	try:
		return html2text(html or "")
	except HTMLParser.HTMLParseError:
		pass


def md_to_html(markdown_text: str) -> Optional["UnicodeWithAttrs"]:
	"""Convert the given markdown text to HTML and returns it."""
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


def markdown(markdown_text: str) -> Optional["UnicodeWithAttrs"]:
	"""Convert the given markdown text to HTML and returns it."""
	return md_to_html(markdown_text)


def is_subset(list_a: list, list_b: list) -> bool:
	"""Return whether list_a is a subset of list_b."""
	return len(list(set(list_a) & set(list_b))) == len(list_a)


def generate_hash(*args, **kwargs) -> str:
	"""Generates a random hash using best available randomness source and returns it.

	You can optionally provide the `length` of the hash to be generated. Default is 56.
	"""
	return frappe.generate_hash(*args, **kwargs)


def sha256_hash(input: str | bytes) -> str:
	"""Return hash of the string using sha256 algorithm."""
	if isinstance(input, str):
		input = input.encode()
	return hashlib.sha256(input).hexdigest()


def dict_with_keys(dict, keys):
	"""Return a new dict with a subset of keys."""
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
		orjson.loads(string)
	except (TypeError, ValueError):
		raise frappe.ValidationError


def parse_json(val: str):
	"""
	Parses json if string else return
	"""
	if isinstance(val, str):
		val = orjson.loads(val)
	if isinstance(val, dict):
		val = frappe._dict(val)
	return val


def orjson_dumps(obj, default=None, option=None, decode=True):
	"""A wrapper around `orjson.dumps`, with some default options set"""

	if option is not None:
		# user defined options are merged with the default options
		option = option | DEFAULT_ORJSON_OPTIONS
	else:
		option = DEFAULT_ORJSON_OPTIONS

	value = orjson.dumps(obj, default, option)
	return value.decode() if decode else value


class _UserInfo(typing.TypedDict):
	email: str
	image: str | None
	name: str


def get_user_info_for_avatar(user_id: str) -> _UserInfo:
	"""Return user info for the given `user_id` suitable for use in an avatar.

	e.g. {
	        "email": "faris@frappe.io",
	        "image": "/assets/frappe/images/ui/avatar.png",
	        "name": "Faris Ansari"
	}
	"""
	try:
		user = frappe.get_cached_doc("User", user_id)
		return {"email": user.email, "image": user.user_image, "name": user.full_name}

	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		return {"email": user_id, "image": "", "name": user_id}


def validate_python_code(string: str, fieldname: str | None = None, is_expression: bool = True) -> None:
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


def format_timedelta(o: datetime.timedelta | str) -> str:
	# MariaDB allows a wide range - https://mariadb.com/kb/en/time/
	# but Frappe doesn't - I think via babel : only allows 0..23 range for hour
	if isinstance(o, datetime.timedelta):
		total_seconds = o.total_seconds()
	else:
		total_seconds = cint(o)
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


def get_job_name(key: str, doctype: str | None = None, doc_name: str | None = None) -> str:
	job_name = key
	if doctype:
		job_name += f"_{doctype}"
	if doc_name:
		job_name += f"_{doc_name}"
	return job_name


def get_imaginary_pixel_response():
	return {
		"type": "binary",
		"filename": "imaginary_pixel.png",
		"filecontent": (
			b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00"
			b"\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\r"
			b"IDATx\x9cc\xf8\xff\xff?\x03\x00\x08\xfc\x02\xfe\xa7\x9a\xa0"
			b"\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
		),
	}


def is_site_link(link: str) -> bool:
	if not link:
		return False
	if link.startswith("/"):
		return True
	return urlparse(link).netloc == urlparse(frappe.utils.get_url()).netloc


def add_trackers_to_url(
	url: str,
	source: str,
	campaign: str | None = None,
	medium: str | None = None,
	content: str | None = None,
) -> str:
	def get_utm_values():
		_source = frappe.db.get_value("UTM Source", source, "slug") or source
		_campaign = frappe.db.get_value("UTM Campaign", campaign, "slug") or campaign
		_medium = frappe.db.get_value("UTM Medium", medium, "slug") or medium
		return _source, _medium, _campaign

	url_parts = list(urlparse(url))
	if url_parts[0] == "mailto":
		return url

	source, medium, campaign = frappe.cache.get_value(
		"utm_" + cstr(source) + "_" + cstr(medium) + "_" + cstr(campaign),
		get_utm_values,
		shared=True,
	)

	trackers = {"utm_source": source}

	if medium:
		trackers["utm_medium"] = medium

	if campaign:
		trackers["utm_campaign"] = campaign

	if content:
		trackers["utm_content"] = content

	query = dict(parse_qsl(url_parts[4])) | trackers

	url_parts[4] = urlencode(query)
	return urlunparse(url_parts)


def parse_and_map_trackers_from_url(url: str, create: bool = False) -> dict:
	query = urlparse(url).query

	url_trackers = dict(parse_qsl(query))

	return map_trackers(url_trackers, create)


def map_trackers(url_trackers: dict, create: bool = False):
	frappe_trackers = {}

	if url_source := url_trackers.get("utm_source", url_trackers.get("source")):
		source = frappe.db.get_value("UTM Source", {"slug": slug(url_source)}, "name") or url_source
		if create and source == url_source and not frappe.db.exists("UTM Source", source):
			source = frappe.new_doc("UTM Source")
			source.name = url_source
			source.description = f"Autogenerated from {url_trackers}"
			source.save(ignore_permissions=True)
		frappe_trackers["utm_source"] = source

	if url_medium := url_trackers.get("utm_medium", url_trackers.get("medium")):
		medium = frappe.db.get_value("UTM Medium", {"slug": slug(url_medium)}, "name") or url_medium
		if create and medium == url_medium and not frappe.db.exists("UTM Medium", medium):
			medium = frappe.new_doc("UTM Medium")
			medium.name = url_medium
			medium.description = f"Autogenerated from {url_trackers}"
			medium.save(ignore_permissions=True)
		frappe_trackers["utm_medium"] = medium

	if url_campaign := url_trackers.get("utm_campaign", url_trackers.get("campaign")):
		campaign = frappe.db.get_value("UTM Campaign", {"slug": slug(url_campaign)}, "name") or url_campaign
		if create and campaign == url_campaign and not frappe.db.exists("UTM Campaign", campaign):
			campaign = frappe.new_doc("UTM Campaign")
			campaign.name = url_campaign
			campaign.campaign_description = f"Autogenerated from {url_trackers}"
			campaign.save(ignore_permissions=True)
		frappe_trackers["utm_campaign"] = campaign

	if url_content := url_trackers.get("utm_content", url_trackers.get("content")):
		frappe_trackers["utm_content"] = url_content

	return frappe_trackers


def bold(text: str | int | float) -> str:
	"""Return `text` wrapped in `<strong>` tags."""
	return f"<strong>{text}</strong>"


def safe_encode(param, encoding="utf-8"):
	try:
		param = param.encode(encoding)
	except Exception:
		pass
	return param


def safe_decode(param, encoding="utf-8", fallback_map: dict | None = None):
	"""
	Method to safely decode data into a string

	:param param: The data to be decoded
	:param encoding: The encoding to decode into
	:param fallback_map: A fallback map to reference in case of a LookupError
	:return:
	"""
	try:
		param = param.decode(encoding)
	except LookupError:
		try:
			param = param.decode((fallback_map or {}).get(encoding, "utf-8"))
		except Exception:
			pass
	except Exception:
		pass
	return param


def as_unicode(text, encoding: str = "utf-8") -> str:
	"""Convert to unicode if required."""
	if isinstance(text, str):
		return text
	elif text is None:
		return ""
	elif isinstance(text, bytes):
		return str(text, encoding)
	else:
		return str(text)


def mock(type, size=1, locale="en"):
	import faker

	results = []
	fake = faker.Faker(locale)
	if type not in dir(fake):
		raise ValueError("Not a valid mock type.")
	else:
		for _ in range(size):
			data = getattr(fake, type)()
			results.append(data)

	from frappe.utils import squashify

	return squashify(results)


# Recursive default dict with arbitrary levels of nesting
def recursive_defaultdict():
	return defaultdict(recursive_defaultdict)


# This is used in test to count memory overhead of default imports.
def _get_rss_memory_usage():
	import psutil

	rss = psutil.Process().memory_info().rss // (1024 * 1024)
	return rss
