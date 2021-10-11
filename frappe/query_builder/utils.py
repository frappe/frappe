from enum import Enum
from typing import Any, Callable, Dict, get_type_hints
from importlib import import_module

from pypika import Query

import frappe
from .builder import MariaDB, Postgres


class db_type_is(Enum):
	MARIADB = "mariadb"
	POSTGRES = "postgres"

class ImportMapper:
	def __init__(self, func_map: Dict[db_type_is, Callable]) -> None:
		self.func_map = func_map

	def __call__(self, *args: Any, **kwds: Any) -> Callable:
		db = db_type_is(frappe.conf.db_type or "mariadb")
		return self.func_map[db](*args, **kwds)

class BuilderIdentificationFailed(Exception):
	def __init__(self):
		super().__init__("Couldn't guess builder")

def get_query_builder(type_of_db: str) -> Query:
	"""[return the query builder object]

	Args:
		type_of_db (str): [string value of the db used]

	Returns:
		Query: [Query object]
	"""
	db = db_type_is(type_of_db)
	picks = {db_type_is.MARIADB: MariaDB, db_type_is.POSTGRES: Postgres}
	return picks[db]

def get_attr(method_string):
	modulename = '.'.join(method_string.split('.')[:-1])
	methodname = method_string.split('.')[-1]
	return getattr(import_module(modulename), methodname)

def patch_query_execute():
	"""Patch the Query Builder with helper execute method
	This excludes the use of `frappe.db.sql` method while
	executing the query object
	"""

	def execute_query(query, *args, **kwargs):
		query = str(query)
		if frappe.flags.in_safe_exec and not query.lower().strip().startswith("select"):
			raise frappe.PermissionError('Only SELECT SQL allowed in scripting')
		return frappe.db.sql(query, *args, **kwargs)

	query_class = get_attr(str(frappe.qb).split("'")[1])
	builder_class = get_type_hints(query_class._builder).get('return')

	if not builder_class:
		raise BuilderIdentificationFailed

	builder_class.run = execute_query
