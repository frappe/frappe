from enum import Enum
from typing import Any, Callable, Dict

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
