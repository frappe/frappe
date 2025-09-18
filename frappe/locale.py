import frappe
from frappe.utils.number_format import NumberFormat


def get_number_format(language: str | None = None) -> NumberFormat:
	"""Return the number format for the given language.

	:param language: The language code to get the value for. Defaults to the current user's language.
	:return: The number format. Defaults to "#,###.##" if not found.
	"""
	number_format = get_locale_value("number_format", language) or "#,###.##"
	return NumberFormat.from_string(number_format)


def get_date_format(language: str | None = None) -> str:
	"""Return the date format for the given language.

	:param language: The language code to get the value for. Defaults to the current user's language.
	:return: The date format string. Defaults to "yyyy-mm-dd" if not found.
	"""
	return get_locale_value("date_format", language) or "yyyy-mm-dd"


def get_time_format(language: str | None = None) -> str:
	"""Return the time format for the given language.

	:param language: The language code to get the value for. Defaults to the current user's language.
	:return: The time format string. Defaults to "HH:mm:ss" if not found.
	"""
	return get_locale_value("time_format", language) or "HH:mm:ss"


def get_first_day_of_the_week(language: str | None = None) -> str:
	"""Return the first day of the week for the given language.

	:param language: The language code to get the value for. Defaults to the current user's language.
	:return: The first day of the week. Defaults to "Sunday" if not found.
	"""
	return get_locale_value("first_day_of_the_week", language) or "Sunday"


def get_locale_value(key: str, language: str | None = None) -> str | None:
	"""Return the value of the key from the Language record or System Settings.

	:param key: The settings key to get the value for.
	:param language: The language code to get the value for. Defaults to the current user's language.
	"""
	lang = language or frappe.local.lang
	if lang:
		value = frappe.client_cache.get_doc("Language", lang).get(key)

	return value or frappe.db.get_default(key)
