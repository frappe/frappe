from enum import Enum
from typing import Any, Callable, Dict, Optional

from pypika import Query

import frappe
from .builder import MariaDB, Postgres


class db_type(Enum):
	MARIADB = "mariadb"
	POSTGRES = "postgres"


class ImportMapper:
	def __init__(self, func_map: Dict[db_type, Callable]) -> None:
		self.func_map = func_map

	def __call__(self, *args: Any, **kwds: Any) -> Callable:
		db = db_type.MARIADB
		if frappe.conf.db_type:
			db = db_type(frappe.conf.db_type)
		return self.func_map[db](*args, **kwds)


def get_query_builder(type_of_db: Optional[str]) -> Query:
	"""[return the query builder object]

	Args:
		type_of_db (str): [string value of the db used]

	Returns:
		Query: [Query object]
	"""
	db = db_type["MARIADB"]
	if type_of_db:
		db = db_type(type_of_db)
	selecter = {db_type.MARIADB: MariaDB, db_type.POSTGRES: Postgres}
	return selecter[db]
