from pypika.functions import *
from pypika.terms import Function
from frappe.query_builder.utils import ImportMapper, db_type_is
from frappe.query_builder.custom import GROUP_CONCAT, STRING_AGG, MATCH, TO_TSVECTOR


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
