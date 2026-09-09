import json
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

MARIADB_TIME_PATTERN = re.compile(
	r"(?P<sign>[+-]?)(?P<hours>\d+):(?P<minutes>[0-5]\d):(?P<seconds>[0-5]\d)(?:\.(?P<fraction>\d+))?"
)

MARIADB_DATE_FORMAT_TOKENS = {
	"%a": "%a",
	"%b": "%b",
	"%d": "%d",
	"%H": "%H",
	"%j": "%j",
	"%M": "%B",
	"%m": "%m",
	"%p": "%p",
	"%S": "%S",
	"%s": "%S",
	"%U": "%U",
	"%u": "%W",
	"%W": "%A",
	"%Y": "%Y",
	"%y": "%y",
}


def convert_sqlite_date(value: bytes) -> date:
	"""Convert a stored SQLite DATE to the value returned by MariaDB drivers."""
	return date.fromisoformat(value.decode().split(" ", 1)[0])


def parse_mariadb_time_duration(value) -> timedelta:
	"""Parse TIME values, including negative durations and durations longer than one day."""
	if isinstance(value, timedelta):
		return value
	if isinstance(value, time):
		return timedelta(
			hours=value.hour,
			minutes=value.minute,
			seconds=value.second,
			microseconds=value.microsecond,
		)
	if isinstance(value, bytes):
		value = value.decode()

	text = str(value)
	match = MARIADB_TIME_PATTERN.fullmatch(text)
	if not match:
		raise ValueError(f"Invalid TIME value: {text!r}")

	fraction = (match["fraction"] or "")[:6].ljust(6, "0")
	duration = timedelta(
		hours=int(match["hours"]),
		minutes=int(match["minutes"]),
		seconds=int(match["seconds"]),
		microseconds=int(fraction or 0),
	)
	return -duration if match["sign"] == "-" else duration


def convert_sqlite_time(value: bytes) -> timedelta:
	"""Convert a stored SQLite TIME to Frappe's timedelta representation."""
	return parse_mariadb_time_duration(value)


def combine_date_with_time_duration(date_value, time_value):
	"""Add a MariaDB-style TIME duration to a date or datetime."""
	if date_value is None or time_value is None:
		return None
	if isinstance(date_value, bytes):
		date_value = date_value.decode()

	try:
		base_datetime = (
			datetime.combine(date_value, time())
			if isinstance(date_value, date) and not isinstance(date_value, datetime)
			else datetime.fromisoformat(str(date_value))
		)
		combined_datetime = base_datetime + parse_mariadb_time_duration(time_value)
	except (TypeError, ValueError):
		return None

	return combined_datetime.isoformat(
		sep=" ", timespec="microseconds" if combined_datetime.microsecond else "seconds"
	)


def _get_sunday_first_week(value: datetime) -> tuple[int, int]:
	"""Return MySQL mode-2 week-year/week: Sunday first, range 1..53."""
	week = int(value.strftime("%U"))
	if week:
		return value.year, week
	previous_year = datetime(value.year - 1, 12, 31)
	return previous_year.year, int(previous_year.strftime("%U"))


def _format_mariadb_date_token(value: datetime, token: str) -> str:
	if strftime_token := MARIADB_DATE_FORMAT_TOKENS.get(token):
		return value.strftime(strftime_token)
	if token == "%c":
		return str(value.month)
	if token == "%D":
		suffix = "th" if 10 < value.day % 100 < 14 else {1: "st", 2: "nd", 3: "rd"}.get(value.day % 10, "th")
		return f"{value.day}{suffix}"
	if token == "%e":
		return str(value.day)
	if token == "%f":
		return f"{value.microsecond:06}"
	if token in {"%h", "%I"}:
		return f"{value.hour % 12 or 12:02}"
	if token == "%i":
		return f"{value.minute:02}"
	if token == "%k":
		return str(value.hour)
	if token == "%l":
		return str(value.hour % 12 or 12)
	if token == "%r":
		return f"{value.hour % 12 or 12:02}:{value.minute:02}:{value.second:02} {'AM' if value.hour < 12 else 'PM'}"
	if token == "%T":
		return f"{value.hour:02}:{value.minute:02}:{value.second:02}"
	if token == "%V":
		return f"{_get_sunday_first_week(value)[1]:02}"
	if token == "%v":
		return f"{value.isocalendar().week:02}"
	if token == "%w":
		return str((value.weekday() + 1) % 7)
	if token == "%X":
		return str(_get_sunday_first_week(value)[0])
	if token == "%x":
		return str(value.isocalendar().year)
	if token == "%%":
		return "%"
	return token[1:]


def format_datetime_with_mariadb_tokens(value, format_string):
	"""Format a date using MariaDB DATE_FORMAT tokens unsupported by SQLite."""
	if value is None or format_string is None:
		return None
	if isinstance(value, bytes):
		value = value.decode()
	if isinstance(format_string, bytes):
		format_string = format_string.decode()
	if isinstance(value, date) and not isinstance(value, datetime):
		value = datetime.combine(value, time())
	elif not isinstance(value, datetime):
		try:
			value = datetime.fromisoformat(str(value))
		except ValueError:
			return None

	formatted_parts = []
	index = 0
	while index < len(format_string):
		if format_string[index] != "%" or index + 1 >= len(format_string):
			formatted_parts.append(format_string[index])
			index += 1
			continue
		formatted_parts.append(_format_mariadb_date_token(value, format_string[index : index + 2]))
		index += 2
	return "".join(formatted_parts)


def _json_value_contains(target, candidate) -> bool:
	if isinstance(target, dict):
		return isinstance(candidate, dict) and all(
			key in target and _json_value_contains(target[key], value) for key, value in candidate.items()
		)
	if isinstance(target, list):
		candidates = candidate if isinstance(candidate, list) else [candidate]
		return all(any(_json_value_contains(value, wanted) for value in target) for wanted in candidates)
	if isinstance(candidate, dict | list):
		return False
	if isinstance(target, bool) or isinstance(candidate, bool):
		return type(target) is type(candidate) and target == candidate
	if isinstance(target, int | float) and isinstance(candidate, int | float):
		return target == candidate
	return type(target) is type(candidate) and target == candidate


def json_contains_mariadb_value(target, candidate):
	"""Return whether one JSON value recursively contains another, following MariaDB semantics."""
	if target is None or candidate is None:
		return None
	if isinstance(target, bytes):
		target = target.decode()
	if isinstance(candidate, bytes):
		candidate = candidate.decode()
	target = json.loads(target) if isinstance(target, str) else target
	candidate = json.loads(candidate) if isinstance(candidate, str) else candidate
	return int(_json_value_contains(target, candidate))


def convert_datetime_to_unix_timestamp(value, session_timezone: ZoneInfo):
	"""Convert a date or datetime to a Unix timestamp in the SQLite session timezone."""
	if value is None:
		return None
	if isinstance(value, bytes):
		value = value.decode()

	try:
		parsed_datetime = (
			datetime.combine(value, time())
			if isinstance(value, date) and not isinstance(value, datetime)
			else datetime.fromisoformat(str(value))
		)
	except (TypeError, ValueError):
		return None

	if parsed_datetime.tzinfo is None:
		parsed_datetime = parsed_datetime.replace(tzinfo=session_timezone)
	return int(parsed_datetime.timestamp())
