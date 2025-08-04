# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import operator
from collections.abc import Callable

import frappe
from frappe.database.utils import NestedSetHierarchy
from frappe.model.db_query import get_timespan_date_range
from frappe.query_builder import Field
from frappe.query_builder.functions import Coalesce


def like(key: Field, value: str) -> frappe.qb:
	"""Wrapper method for `LIKE`

	Args:
	        key (str): field
	        value (str): criterion

	Return:
	        frappe.qb: `frappe.qb` object with `LIKE`
	"""
	return key.like(value)


def func_in(key: Field, value: list | tuple) -> frappe.qb:
	"""Wrapper method for `IN`.

	Args:
	        key (str): field
	        value (Union[int, str]): criterion

	Return:
	        frappe.qb: `frappe.qb` object with `IN`
	"""
	if isinstance(value, str):
		value = value.split(",")
	return key.isin(value)


def not_like(key: Field, value: str) -> frappe.qb:
	"""Wrapper method for `NOT LIKE`.

	Args:
	        key (str): field
	        value (str): criterion

	Return:
	        frappe.qb: `frappe.qb` object with `NOT LIKE`
	"""
	return key.not_like(value)


def func_not_in(key: Field, value: list | tuple | str):
	"""Wrapper method for `NOT IN`.

	Args:
	        key (str): field
	        value (Union[int, str]): criterion

	Return:
	        frappe.qb: `frappe.qb` object with `NOT IN`
	"""
	if isinstance(value, str):
		value = value.split(",")
	return key.notin(value)


def func_regex(key: Field, value: str) -> frappe.qb:
	"""Wrapper method for `REGEX`

	Args:
	        key (str): field
	        value (str): criterion

	Return:
	        frappe.qb: `frappe.qb` object with `REGEX`
	"""
	return key.regex(value)


def func_between(key: Field, value: list | tuple) -> frappe.qb:
	"""Wrapper method for `BETWEEN`.

	Args:
	        key (str): field
	        value (Union[int, str]): criterion

	Return:
	        frappe.qb: `frappe.qb` object with `BETWEEN`
	"""
	return key[slice(*value)]


def func_is(key, value):
	"Wrapper for IS"

	match value.lower():
		case "set":
			return key != ""
		case "not set":
			return key.isnull() | (key == "")
		case _:
			raise ValueError("`is` operator only supports `set` and `not set` as value")


def func_timespan(key: Field, value: str) -> frappe.qb:
	"""Wrapper method for `TIMESPAN`.

	Args:
	        key (str): field
	        value (str): criterion

	Return:
	        frappe.qb: `frappe.qb` object with `TIMESPAN`
	"""

	return func_between(key, get_timespan_date_range(value))


# default operators
OPERATOR_MAP: dict[str, Callable] = {
	"+": operator.add,
	"=": operator.eq,
	"-": operator.sub,
	"!=": operator.ne,
	"<": operator.lt,
	">": operator.gt,
	"<=": operator.le,
	"=<": operator.le,
	">=": operator.ge,
	"=>": operator.ge,
	"/": operator.truediv,
	"*": operator.mul,
	"in": func_in,
	"not in": func_not_in,
	"like": like,
	"not like": not_like,
	"regex": func_regex,
	"between": func_between,
	"is": func_is,
	"timespan": func_timespan,
	# TODO: Add support for custom operators (WIP) - via filters_config hooks
}

NESTED_SET_OPERATORS = frozenset(NestedSetHierarchy)
