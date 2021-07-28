from pypika import MySQLQuery, Order, PostgreSQLQuery, terms
from pypika.queries import Schema, Table

class common:
	terms = terms
	desc = Order.desc
	Schema = Schema

	@staticmethod
	def Table(class_name: str, *args, **kwargs) -> Table:
		if not class_name.startswith("__"):
			class_name = f"tab{class_name}"
		return Table(class_name, *args, **kwargs)


class MariaDB(common, MySQLQuery):
	Field = terms.Field

	@classmethod
	def from_(cls, table, *args, **kwargs):
		if isinstance(table, str):
			table = cls.Table(table)
		return super().from_(table, *args, **kwargs)


class Postgres(common, PostgreSQLQuery):
	field_translation = {"table_name": "relname", "table_rows": "n_tup_ins"}
	schema_translation = {"tables": "pg_stat_all_tables"}

	@classmethod
	def Field(cls, field_name, *args, **kwargs):
		if field_name in cls.field_translation:
			field_name = cls.field_translation[field_name]
		return terms.Field(field_name, *args, **kwargs)

	@classmethod
	def from_(cls, table, *args, **kwargs):
		if isinstance(table, Table):
			if table._schema:
				if table._schema._name == "information_schema":
					table = cls.schema_translation[table._table_name]

		elif isinstance(table, str):
			table = cls.Table(table)

		return super().from_(table, *args, **kwargs)
