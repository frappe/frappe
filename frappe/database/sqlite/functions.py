"""SQLite connection callbacks, registered on every connection by
frappe.database.sqlite.database (see get_connection and create_connection).

Three roles, marked by name:
  - plain names   scalar functions (create_function) emulating the MariaDB SQL
                  functions frappe's queries call, named after the SQL function
  - converter_*   converters (register_converter) turning stored bytes into a Python object
  - adapter_*     adapters (register_adapter) turning a Python object into a stored value
"""

import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

# --- Scalar functions (create_function) ------------------------------------


def regexp(expr, item) -> bool | None:
	"""SQL REGEXP operator: whether item matches the regular expression expr."""
	# NULL on either side yields NULL, as in MariaDB, rather than a TypeError.
	if expr is None or item is None:
		return None
	return re.search(expr, item) is not None


def regexp_replace(item, pattern, repl) -> str | None:
	"""MariaDB REGEXP_REPLACE: replace every match of pattern in item with repl."""
	# NULL in any argument yields NULL, as in MariaDB, rather than a TypeError.
	if item is None or pattern is None or repl is None:
		return None
	return re.sub(pattern, repl, item)


def utc_timestamp() -> str:
	"""MariaDB UTC_TIMESTAMP: the current UTC datetime."""
	# timezone.utc, not datetime.UTC: datetime here is the class, which has no UTC attribute
	return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")  # noqa: UP017


def timestamp(*args) -> str | None:
	"""MariaDB TIMESTAMP: combine a date and a time, or return a single argument as a datetime string."""
	args = [a for a in args if a is not None]
	if not args:
		return None
	if len(args) == 1:
		return str(args[0])
	return f"{args[0]} {args[1]}"


def unix_timestamp(*args) -> int | float:
	"""MariaDB UNIX_TIMESTAMP: epoch seconds for the given datetime, or the current epoch with no argument."""
	from frappe.utils import get_datetime

	epoch = datetime.now().timestamp() if not args or args[0] is None else get_datetime(args[0]).timestamp()
	return int(epoch) if epoch == int(epoch) else epoch


def to_seconds(value) -> int | None:
	"""MariaDB TO_SECONDS: Unix-epoch seconds (absolute epoch irrelevant, only used in differences)."""
	if value is None:
		return None
	from frappe.utils import get_datetime

	return int(get_datetime(value).timestamp())


def datediff(date1, date2) -> int | None:
	"""MariaDB DATEDIFF: whole days between the two dates."""
	if date1 is None or date2 is None:
		return None
	from frappe.utils import getdate

	return (getdate(date1) - getdate(date2)).days


def monthname(value) -> str | None:
	"""MariaDB MONTHNAME: the full month name, for example January."""
	if value is None:
		return None
	from frappe.utils import getdate

	return getdate(value).strftime("%B")


def quarter(value) -> int | None:
	"""MariaDB QUARTER: the quarter of the year, 1 to 4."""
	if value is None:
		return None
	from frappe.utils import getdate

	return (getdate(value).month - 1) // 3 + 1


def date_part(part: str):
	"""Build a scalar function returning a date part, used for MONTH, YEAR and DAY."""

	def fn(value):
		if value is None:
			return None
		from frappe.utils import getdate

		return getattr(getdate(value), part)

	return fn


# MariaDB DATE_FORMAT specifiers that differ from Python strftime.
DATE_FORMAT_MAP = {
	"%i": "%M",  # minutes
	"%s": "%S",  # seconds
	"%M": "%B",  # full month name
	"%h": "%I",  # 12-hour
	"%W": "%A",  # full weekday name
	"%r": "%I:%M:%S %p",
	"%T": "%H:%M:%S",
}


def date_format(value, fmt) -> str | None:
	"""MariaDB DATE_FORMAT via Python strftime, translating the MariaDB specifiers that differ in one pass."""
	if value is None or fmt is None:
		return None
	from frappe.utils import get_datetime

	translated = re.sub(r"%.", lambda m: DATE_FORMAT_MAP.get(m.group(0), m.group(0)), fmt)
	return get_datetime(value).strftime(translated)


def substring_index(value, delim, count) -> str | None:
	"""MariaDB SUBSTRING_INDEX: substring before the count-th delim (from the right if count is negative)."""
	if value is None:
		return None
	value = str(value)
	count = int(count)
	if count == 0:
		return ""
	if count > 0:
		return delim.join(value.split(delim)[:count])
	return delim.join(value.split(delim)[count:])


def timediff(t1, t2) -> str | None:
	"""MariaDB TIMEDIFF: the signed difference t1 - t2 as a TIME string, e.g. '02:30:00' or '-01:00:00'."""
	if t1 is None or t2 is None:
		return None
	from frappe.utils import get_datetime

	try:
		total = int((get_datetime(t1) - get_datetime(t2)).total_seconds())
	except Exception:
		return None
	sign = "-" if total < 0 else ""
	hours, rem = divmod(abs(total), 3600)
	minutes, seconds = divmod(rem, 60)
	return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"


def hour(value) -> int | None:
	"""MariaDB HOUR: the hour of a TIME/datetime; may exceed 23 for a duration such as TIMEDIFF output."""
	if value is None:
		return None
	s = str(value).strip()
	# A [-]H+:MM:SS(.ffffff) TIME string (as timediff emits); MariaDB HOUR() drops the sign.
	if m := re.match(r"-?(\d+):[0-5]?\d:[0-5]?\d(?:\.\d+)?$", s):
		return int(m.group(1))
	from frappe.utils import get_datetime

	try:
		return get_datetime(s).hour
	except Exception:
		return None


# --- Type converters (register_converter) ----------------------------------


def decode_temporal(value: bytes, strict, lenient):
	"""Decode stored bytes into a Python object, trying the strict then lenient parser, else the raw string."""
	s = value.decode()
	try:
		return strict(s)
	except ValueError:
		try:
			return lenient(s)
		except Exception:
			return s


def converter_datetime(value: bytes):
	"""Convert a stored DATETIME or TIMESTAMP value into a Python datetime; see decode_temporal."""
	from frappe.utils import get_datetime

	return decode_temporal(value, datetime.fromisoformat, get_datetime)


def converter_date(value: bytes):
	"""Convert a stored DATE into a Python date (a datetime in a DATE column keeps only its date part)."""
	from frappe.utils import getdate

	return decode_temporal(value, date.fromisoformat, getdate)


def converter_time(value: bytes):
	"""Convert a stored TIME into a timedelta (how the MariaDB driver surfaces TIME columns), or the raw string."""
	from frappe.utils import get_time

	t = decode_temporal(value, time.fromisoformat, get_time)
	if not isinstance(t, time):
		return t
	return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second, microseconds=t.microsecond)


# --- Adapters (register_adapter) -------------------------------------------


def adapter_datetime(value: datetime) -> str:
	"""Serialize a datetime to the space-separated form SQLite stores."""
	return value.isoformat(sep=" ")


def adapter_date(value: date) -> str:
	"""Serialize a date to ISO format."""
	return value.isoformat()


def adapter_time(value: time) -> str:
	"""Serialize a time to ISO format."""
	return value.isoformat()


def adapter_decimal(value: Decimal) -> float:
	"""Serialize a Decimal as a float, matching the REAL storage class."""
	return float(value)


def adapter_timedelta(td: timedelta) -> str:
	"""Serialize a timedelta into a TIME string HH:MM:SS[.ffffff], the inverse of converter_time."""
	# Sign is applied once to the magnitude; divmod on a negative total would misplace it.
	total_us = (td.days * 86400 + td.seconds) * 1_000_000 + td.microseconds
	sign = "-" if total_us < 0 else ""
	seconds, micro = divmod(abs(total_us), 1_000_000)
	hours, rem = divmod(seconds, 3600)
	minutes, seconds = divmod(rem, 60)
	if micro:
		return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}.{micro:06d}"
	return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"
