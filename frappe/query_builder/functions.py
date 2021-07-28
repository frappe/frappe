from pypika.functions import *
from frappe.query_builder.utils import ImportMapper, db_type
from frappe.query_builder.custom import GROUP_CONCAT, STRING_AGG, MATCH, TO_TSVECTOR

GroupConcat = ImportMapper(
	{
		db_type.MARIADB: GROUP_CONCAT,
		db_type.POSTGRES: STRING_AGG
	}
)

Match = ImportMapper(
	{
		db_type.MARIADB: MATCH,
		db_type.POSTGRES: TO_TSVECTOR
	}
)
