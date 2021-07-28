from pypika import MySQLQuery, Order, PostgreSQLQuery, terms
from pypika.queries import Schema, Table

class common:
	terms = terms
	desc = Order.desc
	Schema = Schema

	@staticmethod
	def Table(classname: str, *args, **kwargs) -> Table:
		if not classname.startswith("__"):
			classname = f"tab{classname}"
		return Table(classname, *args, **kwargs)


class MariaDB(common, MySQLQuery):
	Field = terms.Field

	@classmethod
	def from_(cls, class_name, *args, **kwargs):
		if isinstance(class_name, str):
			class_name = f"tab{class_name}"
		return super().from_(class_name, *args, **kwargs)


class Postgres(common, PostgreSQLQuery):
	field_translation = {"table_name": "relname", "table_rows": "n_tup_ins"}
	schema_translation = {"tables": "pg_stat_all_tables"}

	@classmethod
	def Field(cls, fieldName, *args, **kwargs):
		if fieldName in cls.field_translation:
			fieldName = cls.field_translation[fieldName]
		return terms.Field(fieldName, *args, **kwargs)

	@classmethod
	def from_(cls, class_name, *args, **kwargs):
		if isinstance(class_name, Table):
			if class_name._schema:
				if class_name._schema._name == "information_schema":
					class_name = cls.schema_translation[
						class_name._table_name
					]

		elif isinstance(class_name, str):
			class_name = f"tab{class_name}"

		return super().from_(class_name, *args, **kwargs)
