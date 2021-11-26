from pypika.functions import *
from pypika.terms import Function
from frappe.query_builder.utils import ImportMapper, db_type_is
from frappe.query_builder.custom import GROUP_CONCAT, STRING_AGG, MATCH, TO_TSVECTOR
from frappe.database.query import Query
from .utils import Column


class Concat_ws(Function):
	def __init__(self, *terms, **kwargs):
		super(Concat_ws, self).__init__("CONCAT_WS", *terms, **kwargs)


GroupConcat = ImportMapper(
	{
		db_type_is.MARIADB: GROUP_CONCAT,
		db_type_is.POSTGRES: STRING_AGG
	}
)

Match = ImportMapper(
	{
		db_type_is.MARIADB: MATCH,
		db_type_is.POSTGRES: TO_TSVECTOR
	}
)


def max(dt, fieldname, filters=None, **kwargs):
	return (
		Query()
		.build_conditions(dt, filters)
		.select(Max(Column(fieldname)))
		.run(**kwargs)[0][0]
		or 0
	)

def min(dt, fieldname, filters=None, **kwargs):
	return (
		Query()
		.build_conditions(dt, filters)
		.select(Min(Column(fieldname)))
		.run(**kwargs)[0][0]
		or 0
	)

def avg(dt, fieldname, filters=None, **kwargs):
	return (
		Query()
		.build_conditions(dt, filters)
		.select(Avg(Column(fieldname)))
		.run(**kwargs)[0][0]
		or 0
	)

def sum(dt, fieldname, filters=None, **kwargs):
	return (
		Query()
		.build_conditions(dt, filters)
		.select(Sum(Column(fieldname)))
		.run(**kwargs)[0][0]
		or 0
	)