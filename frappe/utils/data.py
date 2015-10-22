# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

# IMPORTANT: only import safe functions as this module will be included in jinja environment
import frappe
import operator
import re, urllib, datetime, math
import babel.dates
from dateutil import parser
from num2words import num2words

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S.%f"
DATETIME_FORMAT = DATE_FORMAT + " " + TIME_FORMAT

# datetime functions
def getdate(string_date=None):
	"""
		 Coverts string date (yyyy-mm-dd) to datetime.date object
	"""
	if not string_date:
		return get_datetime().date()

	if isinstance(string_date, datetime.datetime):
		return string_date.date()

	elif isinstance(string_date, datetime.date):
		return string_date

	# dateutil parser does not agree with dates like 0000-00-00
	if not string_date or string_date=="0000-00-00":
		return None

	return parser.parse(string_date).date()

def get_datetime(datetime_str=None):
	if not datetime_str:
		return now_datetime()

	if isinstance(datetime_str, (datetime.datetime, datetime.timedelta)):
		return datetime_str

	elif isinstance(datetime_str, (list, tuple)):
		return datetime.datetime(datetime_str)

	elif isinstance(datetime_str, datetime.date):
		return datetime.datetime.combine(datetime_str, datetime.time())

	# dateutil parser does not agree with dates like 0000-00-00
	if not datetime_str or (datetime_str or "").startswith("0000-00-00"):
		return None

	return parser.parse(datetime_str)

def to_timedelta(time_str):
	if isinstance(time_str, basestring):
		t = parser.parse(time_str)
		return datetime.timedelta(hours=t.hour, minutes=t.minute, seconds=t.second, microseconds=t.microsecond)

	else:
		return time_str

def add_to_date(date, years=0, months=0, days=0):
	"""Adds `days` to the given date"""
	from dateutil.relativedelta import relativedelta

	as_string, as_datetime = False, False
	if isinstance(date, basestring):
		as_string = True
		if " " in date:
			as_datetime = True
		date = parser.parse(date)

	date = date + relativedelta(years=years, months=months, days=days)

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

def time_diff(string_ed_date, string_st_date):
	return get_datetime(string_ed_date) - get_datetime(string_st_date)

def time_diff_in_seconds(string_ed_date, string_st_date):
	return time_diff(string_ed_date, string_st_date).total_seconds()

def time_diff_in_hours(string_ed_date, string_st_date):
	return round(float(time_diff(string_ed_date, string_st_date).total_seconds()) / 3600, 6)

def now_datetime():
	return convert_utc_to_user_timezone(datetime.datetime.utcnow())

def _get_time_zone():
	time_zone = (frappe.db.get_single_value("System Settings", "time_zone")
		or "Asia/Kolkata")

	return time_zone

def get_time_zone():
	if frappe.local.flags.in_test:
		return _get_time_zone()

	return frappe.cache().get_value("time_zone", _get_time_zone)

def convert_utc_to_user_timezone(utc_timestamp):
	from pytz import timezone, UnknownTimeZoneError
	utcnow = timezone('UTC').localize(utc_timestamp)
	try:
		return utcnow.astimezone(timezone(get_time_zone()))
	except UnknownTimeZoneError:
		return utcnow

def now():
	"""return current datetime as yyyy-mm-dd hh:mm:ss"""
	if getattr(frappe.local, "current_date", None):
		return getdate(frappe.local.current_date).strftime(DATE_FORMAT) + " " + \
			now_datetime().strftime(TIME_FORMAT)
	else:
		return now_datetime().strftime(DATETIME_FORMAT)

def nowdate():
	"""return current date as yyyy-mm-dd"""
	return now_datetime().strftime(DATE_FORMAT)

def today():
	return nowdate()

def nowtime():
	"""return current time in hh:mm"""
	return now_datetime().strftime(TIME_FORMAT)

def get_first_day(dt, d_years=0, d_months=0):
	"""
	 Returns the first day of the month for the date specified by date object
	 Also adds `d_years` and `d_months` if specified
	"""
	dt = getdate(dt)

	# d_years, d_months are "deltas" to apply to dt
	overflow_years, month = divmod(dt.month + d_months - 1, 12)
	year = dt.year + d_years + overflow_years

	return datetime.date(year, month + 1, 1)

def get_last_day(dt):
	"""
	 Returns last day of the month using:
	 `get_first_day(dt, 0, 1) + datetime.timedelta(-1)`
	"""
	return get_first_day(dt, 0, 1) + datetime.timedelta(-1)


def get_time(time_str):
	if isinstance(time_str, datetime.datetime):
		return time_str.time()
	elif isinstance(time_str, datetime.time):
		return time_str
	return parser.parse(time_str).time()

def get_datetime_str(datetime_obj):
	if isinstance(datetime_obj, basestring):
		datetime_obj = get_datetime(datetime_obj)

	return datetime_obj.strftime(DATETIME_FORMAT)

def get_user_format():
	if getattr(frappe.local, "user_format", None) is None:
		frappe.local.user_format = frappe.db.get_default("date_format")

	return frappe.local.user_format or "yyyy-mm-dd"

def formatdate(string_date=None, format_string=None):
	"""
	 	Convers the given string date to :data:`user_format`
		User format specified in defaults

		 Examples:

		 * dd-mm-yyyy
		 * mm-dd-yyyy
		 * dd/mm/yyyy
	"""
	date = getdate(string_date) if string_date else now_datetime().date()
	if not format_string:
		format_string = get_user_format().replace("mm", "MM")

	return babel.dates.format_date(date, format_string, locale=(frappe.local.lang or "").replace("-", "_"))

def format_time(txt):
	return babel.dates.format_time(get_time(txt), locale=(frappe.local.lang or "").replace("-", "_"))

def format_datetime(datetime_string, format_string=None):
	if not datetime_string:
		return

	datetime = get_datetime(datetime_string)
	if not format_string:
		format_string = get_user_format().replace("mm", "MM") + " HH:mm:ss"

	return babel.dates.format_datetime(datetime, format_string, locale=(frappe.local.lang or "").replace("-", "_"))

def global_date_format(date):
	"""returns date as 1 January 2012"""
	formatted_date = getdate(date).strftime("%d %B %Y")
	return formatted_date.startswith("0") and formatted_date[1:] or formatted_date

def has_common(l1, l2):
	"""Returns truthy value if there are common elements in lists l1 and l2"""
	return set(l1) & set(l2)

def flt(s, precision=None):
	"""Convert to float (ignore commas)"""
	if isinstance(s, basestring):
		s = s.replace(',','')

	try:
		num = float(s)
		if precision is not None:
			num = rounded(num, precision)
	except Exception:
		num = 0

	return num

def cint(s):
	"""Convert to integer"""
	try: num = int(float(s))
	except: num = 0
	return num

def cstr(s):
	if isinstance(s, unicode):
		return s
	elif s==None:
		return ''
	elif isinstance(s, basestring):
		return unicode(s, 'utf-8')
	else:
		return unicode(s)

def rounded(num, precision=0):
	"""round method for round halfs to nearest even algorithm aka banker's rounding - compatible with python3"""
	precision = cint(precision)
	multiplier = 10 ** precision

	# avoid rounding errors
	num = round(num * multiplier if precision else num, 8)

	floor = math.floor(num)
	decimal_part = num - floor

	if not precision and decimal_part == 0.5:
		num = floor if (floor % 2 == 0) else floor + 1
	else:
		num = round(num)

	return (num / multiplier) if precision else num

def encode(obj, encoding="utf-8"):
	if isinstance(obj, list):
		out = []
		for o in obj:
			if isinstance(o, unicode):
				out.append(o.encode(encoding))
			else:
				out.append(o)
		return out
	elif isinstance(obj, unicode):
		return obj.encode(encoding)
	else:
		return obj

def parse_val(v):
	"""Converts to simple datatypes from SQL query results"""
	if isinstance(v, (datetime.date, datetime.datetime)):
		v = unicode(v)
	elif isinstance(v, datetime.timedelta):
		v = ":".join(unicode(v).split(":")[:2])
	elif isinstance(v, long):
		v = int(v)
	return v

def fmt_money(amount, precision=None, currency=None):
	"""
	Convert to string with commas for thousands, millions etc
	"""
	number_format = None
	if currency:
		number_format = frappe.db.get_value("Currency", currency, "number_format", cache=True)

	if not number_format:
		number_format = frappe.db.get_default("number_format") or "#,###.##"

	decimal_str, comma_str, number_format_precision = get_number_format_info(number_format)

	if precision is None:
		precision = number_format_precision

	amount = '%.*f' % (precision, flt(amount))
	if amount.find('.') == -1:
		decimals = ''
	else:
		decimals = amount.split('.')[1]

	parts = []
	minus = ''
	if flt(amount) < 0:
		minus = '-'

	amount = cstr(abs(flt(amount))).split('.')[0]

	if len(amount) > 3:
		parts.append(amount[-3:])
		amount = amount[:-3]

		val = number_format=="#,##,###.##" and 2 or 3

		while len(amount) > val:
			parts.append(amount[-val:])
			amount = amount[:-val]

	parts.append(amount)

	parts.reverse()

	amount = comma_str.join(parts) + ((precision and decimal_str) and (decimal_str + decimals) or "")
	amount = minus + amount

	if currency and frappe.defaults.get_global_default("hide_currency_symbol") != "Yes":
		symbol = frappe.db.get_value("Currency", currency, "symbol") or currency
		amount = symbol + " " + amount

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
	"#,###": ("", ",", 0)
}

def get_number_format_info(format):
	return number_format_info.get(format) or (".", ",", 2)

#
# convet currency to words
#
def money_in_words(number, main_currency = None, fraction_currency=None):
	"""
	Returns string in words with currency and fraction currency.
	"""
	from frappe.utils import get_defaults
	_ = frappe._

	if not number or flt(number) < 0:
		return ""

	d = get_defaults()
	if not main_currency:
		main_currency = d.get('currency', 'INR')
	if not fraction_currency:
		fraction_currency = frappe.db.get_value("Currency", main_currency, "fraction") or _("Cent")

	n = "%.2f" % flt(number)
	main, fraction = n.split('.')
	if len(fraction)==1: fraction += '0'


	number_format = frappe.db.get_value("Currency", main_currency, "number_format", cache=True) or \
		frappe.db.get_default("number_format") or "#,###.##"

	in_million = True
	if number_format == "#,##,###.##": in_million = False

	out = main_currency + ' ' + in_words(main, in_million).title()
	if cint(fraction):
		out = out + ' ' + _('and') + ' ' + in_words(fraction, in_million).title() + ' ' + fraction_currency

	return out + ' ' + _('only.')

#
# convert number to words
#
def in_words(integer, in_million=True):
	"""
	Returns string in words for the given integer.
	"""
	locale = 'en_IN' if not in_million else frappe.local.lang
	integer = int(integer)
	try:
		ret = num2words(integer, lang=locale)
	except NotImplementedError:
		ret = num2words(integer, lang='en')
	return ret.replace('-', ' ')

def is_html(text):
	out = False
	for key in ["<br>", "<p", "<img", "<div"]:
		if key in text:
			out = True
			break
	return out


# from Jinja2 code
_striptags_re = re.compile(r'(<!--.*?-->|<[^>]*>)')
def strip_html(text):
	"""removes anything enclosed in and including <>"""
	return _striptags_re.sub("", text)

def escape_html(text):
	html_escape_table = {
		"&": "&amp;",
		'"': "&quot;",
		"'": "&apos;",
		">": "&gt;",
		"<": "&lt;",
	}

	return "".join(html_escape_table.get(c,c) for c in text)

def pretty_date(iso_datetime):
	"""
		Takes an ISO time and returns a string representing how
		long ago the date represents.
		Ported from PrettyDate by John Resig
	"""
	if not iso_datetime: return ''
	import math

	if isinstance(iso_datetime, basestring):
		iso_datetime = datetime.datetime.strptime(iso_datetime, DATETIME_FORMAT)
	now_dt = datetime.datetime.strptime(now(), DATETIME_FORMAT)
	dt_diff = now_dt - iso_datetime

	# available only in python 2.7+
	# dt_diff_seconds = dt_diff.total_seconds()

	dt_diff_seconds = dt_diff.days * 86400.0 + dt_diff.seconds

	dt_diff_days = math.floor(dt_diff_seconds / 86400.0)

	# differnt cases
	if dt_diff_seconds < 60.0:
		return 'just now'
	elif dt_diff_seconds < 120.0:
		return '1 minute ago'
	elif dt_diff_seconds < 3600.0:
		return '%s minutes ago' % cint(math.floor(dt_diff_seconds / 60.0))
	elif dt_diff_seconds < 7200.0:
		return '1 hour ago'
	elif dt_diff_seconds < 86400.0:
		return '%s hours ago' % cint(math.floor(dt_diff_seconds / 3600.0))
	elif dt_diff_days == 1.0:
		return 'Yesterday'
	elif dt_diff_days < 7.0:
		return '%s days ago' % cint(dt_diff_days)
	elif dt_diff_days < 31.0:
		return '%s week(s) ago' % cint(math.ceil(dt_diff_days / 7.0))
	elif dt_diff_days < 365.0:
		return '%s months ago' % cint(math.ceil(dt_diff_days / 30.0))
	else:
		return 'more than %s year(s) ago' % cint(math.floor(dt_diff_days / 365.0))

def comma_or(some_list):
	return comma_sep(some_list, frappe._("{0} or {1}"))

def comma_and(some_list):
	return comma_sep(some_list, frappe._("{0} and {1}"))

def comma_sep(some_list, pattern):
	if isinstance(some_list, (list, tuple)):
		# list(some_list) is done to preserve the existing list
		some_list = [unicode(s) for s in list(some_list)]
		if not some_list:
			return ""
		elif len(some_list) == 1:
			return some_list[0]
		else:
			some_list = ["'%s'" % s for s in some_list]
			return pattern.format(", ".join(frappe._(s) for s in some_list[:-1]), some_list[-1])
	else:
		return some_list

def filter_strip_join(some_list, sep):
	"""given a list, filter None values, strip spaces and join"""
	return (cstr(sep)).join((cstr(a).strip() for a in filter(None, some_list)))

def get_url(uri=None, full_address=False):
	"""get app url from request"""
	host_name = frappe.local.conf.host_name

	if uri and (uri.startswith("http://") or uri.startswith("https://")):
		return uri

	if not host_name:
		if hasattr(frappe.local, "request") and frappe.local.request and frappe.local.request.host:
			protocol = 'https' == frappe.get_request_header('X-Forwarded-Proto', "") and 'https://' or 'http://'
			host_name = protocol + frappe.local.request.host
		elif frappe.local.site:
			host_name = "http://{}".format(frappe.local.site)
		else:
			host_name = frappe.db.get_value("Website Settings", "Website Settings",
				"subdomain")
			if host_name and "http" not in host_name:
				host_name = "http://" + host_name

			if not host_name:
				host_name = "http://localhost"

	if not uri and full_address:
		uri = frappe.get_request_header("REQUEST_URI", "")

	url = urllib.basejoin(host_name, uri) if uri else host_name

	return url

def get_host_name():
	return get_url().rsplit("//", 1)[-1]

def get_link_to_form(doctype, name, label=None):
	if not label: label = name

	return """<a href="{0}">{1}</a>""".format(get_url_to_form(doctype, name), label)

def get_url_to_form(doctype, name):
	return get_url(uri = "desk#Form/{0}/{1}".format(doctype, name))

def get_url_to_list(doctype):
	return get_url(uri = "desk#List/{0}".format(doctype))

operator_map = {
	# startswith
	"^": lambda (a, b): (a or "").startswith(b),

	# in or not in a list
	"in": lambda (a, b): operator.contains(b, a),
	"not in": lambda (a, b): not operator.contains(b, a),

	# comparison operators
	"=": lambda (a, b): operator.eq(a, b),
	"!=": lambda (a, b): operator.ne(a, b),
	">": lambda (a, b): operator.gt(a, b),
	"<": lambda (a, b): operator.lt(a, b),
	">=": lambda (a, b): operator.ge(a, b),
	"<=": lambda (a, b): operator.le(a, b),
	"not None": lambda (a, b): a and True or False,
	"None": lambda (a, b): (not a) and True or False
}

def compare(val1, condition, val2):
	ret = False
	if condition in operator_map:
		ret = operator_map[condition]((val1, val2))

	return ret

def scrub_urls(html):
	html = expand_relative_urls(html)
	# encoding should be responsibility of the composer
	# html = quote_urls(html)
	return html

def expand_relative_urls(html):
	# expand relative urls
	url = get_url()
	if url.endswith("/"): url = url[:-1]

	def _expand_relative_urls(match):
		to_expand = list(match.groups())
		if not to_expand[2].startswith("/"):
			to_expand[2] = "/" + to_expand[2]
		to_expand.insert(2, url)
		return "".join(to_expand)

	return re.sub('(href|src){1}([\s]*=[\s]*[\'"]?)((?!http)[^\'" >]+)([\'"]?)', _expand_relative_urls, html)

def quoted(url):
	return cstr(urllib.quote(encode(url), safe=b"~@#$&()*!+=:;,.?/'"))

def quote_urls(html):
	def _quote_url(match):
		groups = list(match.groups())
		groups[2] = quoted(groups[2])
		return "".join(groups)
	return re.sub('(href|src){1}([\s]*=[\s]*[\'"]?)((?:http)[^\'">]+)([\'"]?)',
		_quote_url, html)

def unique(seq):
	"""use this instead of list(set()) to preserve order of the original list.
	Thanks to Stackoverflow: http://stackoverflow.com/questions/480214/how-do-you-remove-duplicates-from-a-list-in-python-whilst-preserving-order"""

	seen = set()
	seen_add = seen.add
	return [ x for x in seq if not (x in seen or seen_add(x)) ]

def strip(val, chars=None):
	# \ufeff is no-width-break, \u200b is no-width-space
	return (val or "").replace("\ufeff", "").replace("\u200b", "").strip(chars)
