from pypika.functions import *
from pypika.terms import Arithmetic, ArithmeticExpression, CustomFunction, Function

from frappe.query_builder.custom import GROUP_CONCAT, MATCH, STRING_AGG, TO_TSVECTOR
from frappe.query_builder.utils import ImportMapper, db_type_is

from .utils import Column


class Concat_ws(Function):
	def __init__(self, *terms, **kwargs):
		super(Concat_ws, self).__init__("CONCAT_WS", *terms, **kwargs)


GroupConcat = ImportMapper({db_type_is.MARIADB: GROUP_CONCAT, db_type_is.POSTGRES: STRING_AGG})

Match = ImportMapper({db_type_is.MARIADB: MATCH, db_type_is.POSTGRES: TO_TSVECTOR})


class _PostgresTimestamp(ArithmeticExpression):
	def __init__(self, datepart, timepart, alias=None):
		if isinstance(datepart, str):
			datepart = Cast(datepart, "date")
		if isinstance(timepart, str):
			timepart = Cast(timepart, "time")

		super().__init__(operator=Arithmetic.add, left=datepart, right=timepart, alias=alias)


CombineDatetime = ImportMapper(
	{
		db_type_is.MARIADB: CustomFunction("TIMESTAMP", ["date", "time"]),
		db_type_is.POSTGRES: _PostgresTimestamp,
	}
)
