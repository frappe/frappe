from pypika import MySQLQuery, Order, PostgreSQLQuery
from pypika import functions as fn
from pypika import terms
from pypika.queries import Schema, Table

def qb(db_type):
	if not db_type:
		db_type = "mariadb"
	selecter = {"mariadb": MariaDB, "postgres": Postgres}
	return selecter[db_type]

class common:
	fn = fn
	terms = terms
	desc = Order.desc
	Schema = Schema

class MariaDB(MySQLQuery,common):
	Field = terms.Field

	def __init__(self) -> None:
		super().__init__()
	
	@classmethod
	def from_(cls, class_name, *args, **kwargs):
		if isinstance(class_name,str):
			class_name = "tab"+class_name
		return super().from_(class_name, *args, **kwargs)
	
	@staticmethod
	def rename_table(old_name, new_name):
		return f"RENAME TABLE `tab{old_name}` TO `tab{new_name}`"

	@staticmethod
	def DESC(dt):
		return f"DESC `tab{dt}`"

class Postgres(PostgreSQLQuery,common):
	postgres_field = {"table_name": "relname", "table_rows": "n_tup_ins"}
	information_schema_translation = {"tables": "pg_stat_all_tables"}

	def __init__(self) -> None:
		super().__init__()

	@classmethod
	def Field(cls, fieldName, *args, **kwargs):
		if fieldName in cls.postgres_field:
			fieldName = cls.postgres_field[fieldName]
		return terms.Field(fieldName, *args, **kwargs)

	@classmethod
	def from_(cls, class_name, *args, **kwargs):
		if isinstance(class_name, Table):
			if class_name._schema:
				if class_name._schema._name == "information_schema":
					class_name = cls.information_schema_translation[class_name._table_name]

		elif isinstance(class_name, str):
			class_name = "tab" + class_name

		return super().from_(class_name, *args, **kwargs)
	
	@staticmethod
	def rename_table(old_name, new_name):
		return f"ALTER TABLE `tab{old_name}` RENAME TO `tab{new_name}`"
	
	@staticmethod
	def DESC(dt):
		return f"SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_NAME = 'tab{dt}'"
