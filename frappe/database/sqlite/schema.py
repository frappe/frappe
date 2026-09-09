import frappe
from frappe import _
from frappe.database.schema import DBTable
from frappe.utils.defaults import get_not_null_defaults


class SQLiteTable(DBTable):
	def create(self):
		# First prepare the basic table creation without indexes
		additional_definitions = []
		name_column = "name TEXT PRIMARY KEY"

		# columns
		column_defs = self.get_column_definitions()
		if column_defs:
			additional_definitions += column_defs

		index_defs = []  # Store index definitions separately

		# child table columns
		if self.meta.get("istable", default=0):
			additional_definitions.extend(["parent TEXT", "parentfield TEXT", "parenttype TEXT"])
			index_defs.append(f"CREATE INDEX `{self.table_name}_parent_idx` ON `{self.table_name}`(parent)")
		else:
			# parent types
			index_defs.append(
				f"CREATE INDEX `{self.table_name}_creation_idx` ON `{self.table_name}`(creation)"
			)
			if self.meta.sort_field == "modified":
				index_defs.append(
					f"CREATE INDEX `{self.table_name}_modified_idx` ON `{self.table_name}`(modified)"
				)

		# creating sequence(s)
		if not self.meta.issingle and self.meta.autoname == "autoincrement":
			name_column = "name INTEGER PRIMARY KEY AUTOINCREMENT"
		elif not self.meta.issingle and self.meta.autoname == "UUID":
			name_column = "name TEXT PRIMARY KEY"

		additional_definitions = ",\n".join(additional_definitions)

		# create table
		create_table_query = f"""CREATE TABLE `{self.table_name}` (
			{name_column},
			creation DATETIME,
			modified DATETIME,
			modified_by TEXT,
			owner TEXT,
			docstatus INTEGER NOT NULL DEFAULT 0,
			idx INTEGER NOT NULL DEFAULT 0,
			{additional_definitions})"""

		# Execute table creation
		frappe.db.sql_ddl(create_table_query)

		# Create indexes separately
		for index_query in index_defs:
			frappe.db.sql_ddl(index_query)

	def alter(self):
		from frappe.database.sqlite.database import get_column_definition, rebuild_table

		for col in self.columns.values():
			col.build_for_alter_table(self.current_columns.get(col.fieldname.lower()))

		primary_key_type = self.alter_primary_key()
		new_column_names = {col.fieldname for col in self.add_column}
		requires_rebuild = bool(
			self.change_type
			or self.set_default
			or self.change_nullability
			or self.drop_unique
			or primary_key_type
			or any(col.unique for col in self.add_column)
		)

		index_queries = self.get_index_queries(new_column_names)
		if not requires_rebuild:
			queries = [
				f"ALTER TABLE `{self.table_name}` ADD COLUMN `{col.fieldname}` {col.get_definition()}"
				for col in self.add_column
			]
			queries.extend(self.get_drop_index_queries())
			queries.extend(index_queries)
			self.run_schema_queries(queries)
			return

		current_columns = frappe.db.sql(f"PRAGMA table_info(`{self.table_name}`)", as_dict=True)
		column_names = [column.name for column in current_columns]
		column_definitions = [get_column_definition(column) for column in current_columns]

		columns_to_modify = set(self.change_type + self.set_default + self.change_nullability)
		for col in columns_to_modify:
			for index, column in enumerate(current_columns):
				if column.name == col.fieldname:
					column_definitions[index] = (
						f"`{col.fieldname}` {col.get_definition(for_modification=True)}"
					)
					break

		if primary_key_type:
			for index, column in enumerate(current_columns):
				if column.name == "name":
					column_definitions[index] = f"`name` {primary_key_type}"
					break

		column_definitions.extend(f"`{col.fieldname}` {col.get_definition()}" for col in self.add_column)

		pre_rebuild_queries = []
		for col in self.change_nullability:
			if not col.not_nullable:
				continue
			default = col.default or get_not_null_defaults(col.fieldtype)
			if isinstance(default, str):
				default = frappe.db.escape(default)
			pre_rebuild_queries.append(
				f"UPDATE `{self.table_name}` SET `{col.fieldname}` = {default} "
				f"WHERE `{col.fieldname}` IS NULL"
			)

		rebuild_table(
			self.table_name,
			column_definitions,
			column_names,
			drop_index_fields={col.fieldname for col in self.drop_index},
			drop_unique_fields={col.fieldname for col in self.drop_unique},
			pre_rebuild_queries=pre_rebuild_queries,
			post_rebuild_queries=index_queries,
		)

	def get_index_queries(self, new_column_names: set[str]) -> list[str]:
		queries = [
			f"CREATE UNIQUE INDEX IF NOT EXISTS `{self.table_name}_{col.fieldname}_unique` "
			f"ON `{self.table_name}` (`{col.fieldname}`)"
			for col in self.add_unique
			if col.fieldname not in new_column_names
		]
		queries.extend(
			f"CREATE INDEX IF NOT EXISTS `{self.table_name}_{col.fieldname}_index` "
			f"ON `{self.table_name}` (`{col.fieldname}`)"
			for col in self.add_index
			if not frappe.db.get_column_index(self.table_name, col.fieldname, unique=False)
		)
		if self.meta.sort_field == "modified" and not frappe.db.get_column_index(
			self.table_name, "modified", unique=False
		):
			queries.append(
				f"CREATE INDEX IF NOT EXISTS `{self.table_name}_modified_idx` "
				f"ON `{self.table_name}` (`modified`)"
			)
		return queries

	def get_drop_index_queries(self) -> list[str]:
		queries = []
		for col in self.drop_index:
			if col.fieldname == "name":
				continue
			for index in frappe.db.sql(f"PRAGMA index_list(`{self.table_name}`)", as_dict=True):
				if index.origin == "pk" or index.partial or index.unique:
					continue
				index_columns = frappe.db.sql(f"PRAGMA index_info(`{index.name}`)", as_dict=True)
				if len(index_columns) == 1 and index_columns[0].name == col.fieldname:
					queries.append(f"DROP INDEX `{index.name}`")
		return list(dict.fromkeys(queries))

	@staticmethod
	def run_schema_queries(queries: list[str]) -> None:
		if not queries:
			return
		frappe.db.commit()
		try:
			for query in queries:
				frappe.db.sql(query)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			raise

	def alter_primary_key(self) -> str | None:
		autoname = self.meta.autoname
		current_type = frappe.db.get_column_type(self.doctype, "name") or ""
		current_base_type = current_type.partition("(")[0]
		if autoname == "UUID" and current_base_type != "uuid":
			return "uuid"

		if autoname != "UUID" and current_base_type == "uuid":
			return f"varchar({frappe.db.VARCHAR_LEN})"
