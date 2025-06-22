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
		for col in self.columns.values():
			col.build_for_alter_table(self.current_columns.get(col.fieldname.lower()))

		for col in self.add_column:
			frappe.db.sql_ddl(
				f"ALTER TABLE `{self.table_name}` ADD COLUMN `{col.fieldname}` {col.get_definition()}"
			)

		if not (
			self.change_type
			or self.set_default
			or self.change_nullability
			or self.add_index
			or self.add_unique
			or self.drop_index
			or self.drop_unique
		):
			return

		# Get current table column definitions
		existing_columns = []
		for column in frappe.db.sql(f"PRAGMA table_info(`{self.table_name}`)", as_dict=1):
			existing_columns.append(f"`{column.name}` {column.type}")

		columns = existing_columns.copy()

		# Modify existing columns
		columns_to_modify = set(self.change_type + self.set_default + self.change_nullability)
		for col in columns_to_modify:
			# Replace the old column definition with the new one
			for i, column in enumerate(columns):
				if column.startswith(f"`{col.fieldname}`"):
					columns[i] = f"`{col.fieldname}` {col.get_definition(for_modification=True)}"
					break

		# Create new table
		temp_table = f"{self.table_name}_new"
		create_table = f"CREATE TABLE `{temp_table}` (\n{','.join(columns)}\n)"
		frappe.db.sql_ddl(create_table)

		# Copy data
		existing_columns = [col.split()[0] for col in existing_columns]
		column_list = ", ".join(existing_columns)
		frappe.db.sql_ddl(f"INSERT INTO `{temp_table}` SELECT {column_list} FROM `{self.table_name}`")

		# Drop old table
		frappe.db.sql_ddl(f"DROP TABLE `{self.table_name}`")

		# Rename new table
		frappe.db.sql_ddl(f"ALTER TABLE `{temp_table}` RENAME TO `{self.table_name}`")

		# Recreate indexes
		index_queries = []
		if self.add_unique:
			index_queries.extend(
				f"CREATE UNIQUE INDEX IF NOT EXISTS `{col.fieldname}` ON `{self.table_name}` (`{col.fieldname}`)"
				for col in self.add_unique
			)
		if self.add_index:
			index_queries.extend(
				f"CREATE INDEX IF NOT EXISTS `{col.fieldname}_index` ON `{self.table_name}` (`{col.fieldname}`)"
				for col in self.add_index
				if not frappe.db.get_column_index(self.table_name, col.fieldname, unique=False)
			)
		if self.meta.sort_field == "modified" and not frappe.db.get_column_index(
			self.table_name, "modified", unique=False
		):
			index_queries.append(f"CREATE INDEX `modified` ON `{self.table_name}` (`modified`)")

		for query in index_queries:
			frappe.db.sql_ddl(query)

	def alter_primary_key(self) -> str | None:
		# If there are no values in table allow migrating to UUID from TEXT
		autoname = self.meta.autoname
		if autoname == "UUID" and frappe.db.get_column_type(self.doctype, "name") != "TEXT":
			if not frappe.db.get_value(self.doctype, {}, order_by=None):
				return "ALTER COLUMN name TEXT"
			else:
				frappe.throw(
					_("Primary key of doctype {0} can not be changed as there are existing values.").format(
						self.doctype
					)
				)

		# Reverting from UUID to TEXT
		if autoname != "UUID" and frappe.db.get_column_type(self.doctype, "name") == "TEXT":
			return "ALTER COLUMN name TEXT"
