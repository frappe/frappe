import re

import frappe
from frappe import _
from frappe.database.schema import DBTable
from frappe.utils.defaults import get_not_null_defaults


class SQLiteTable(DBTable):
	def get_column_definitions(self):
		# Uniqueness is enforced through explicit named indexes (get_column_index_queries), so
		# suppress the inline UNIQUE the base definition would add. Otherwise SQLite also builds a
		# redundant sqlite_autoindex_* for the column, leaving two unique indexes per field.
		column_list = [*frappe.db.DEFAULT_COLUMNS]
		ret = []
		for k in list(self.columns):
			if k not in column_list:
				d = self.columns[k].get_definition(for_modification=True)
				if d:
					ret.append(f"`{k}` {d}")
					column_list.append(k)
		return ret

	def name_column_definition(self) -> str:
		"""Definition for the primary-key `name` column.

		`autoincrement` doctypes need a rowid-backed `INTEGER PRIMARY KEY AUTOINCREMENT`; everything
		else (including UUID) is a `TEXT PRIMARY KEY`. Shared by create() and the alter() rebuild so
		the primary key is never silently dropped when a table is reconstructed."""
		if not self.meta.issingle and self.meta.autoname == "autoincrement":
			return "name INTEGER PRIMARY KEY AUTOINCREMENT"
		return "name TEXT PRIMARY KEY"

	def create(self):
		# First prepare the basic table creation without indexes
		additional_definitions = []
		name_column = self.name_column_definition()

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

		index_defs.extend(self.get_column_index_queries())

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
			# SQLite rejects ADD COLUMN with an inline UNIQUE constraint ("Cannot add a UNIQUE
			# column"); the unique/search index is created separately via add_unique/add_index.
			frappe.db.sql_ddl(
				f"ALTER TABLE `{self.table_name}` ADD COLUMN `{col.fieldname}` {col.get_definition(for_modification=True)}"
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

		# Get current table column definitions. SQLite has no ALTER for constraints, so the table is
		# rebuilt -- and PRAGMA table_info reports column name/type but not the PRIMARY KEY clause, so
		# it has to be re-emitted explicitly or the rebuild silently drops the primary key.
		existing_columns = []
		extra_pk_columns = []
		for column in frappe.db.sql(f"PRAGMA table_info(`{self.table_name}`)", as_dict=1):
			if column.name == "name":
				existing_columns.append(f"`name` {self.name_column_definition().split(' ', 1)[1]}")
			else:
				existing_columns.append(f"`{column.name}` {column.type}")
				# Preserve any non-name primary key columns (e.g. composite keys) via a table-level
				# constraint added below.
				if column.pk:
					extra_pk_columns.append((column.pk, column.name))

		columns = existing_columns.copy()
		if extra_pk_columns:
			pk_cols = ", ".join(f"`{name}`" for _, name in sorted(extra_pk_columns))
			columns.append(f"PRIMARY KEY ({pk_cols})")

		# Modify existing columns
		columns_to_modify = set(self.change_type + self.set_default + self.change_nullability)
		for col in columns_to_modify:
			# Replace the old column definition with the new one
			for i, column in enumerate(columns):
				if column.startswith(f"`{col.fieldname}`"):
					columns[i] = f"`{col.fieldname}` {col.get_definition(for_modification=True)}"
					break

		# Rebuilding the table drops user-defined indexes, so capture them first.
		preserved_indexes = self.get_indexes_to_preserve()

		# Create new table
		temp_table = f"{self.table_name}_new"
		create_table = f"CREATE TABLE `{temp_table}` (\n{','.join(columns)}\n)"
		frappe.db.sql_ddl(create_table)

		# Copy data, coalescing NULLs to the column default for any column gaining a NOT NULL
		# constraint -- an existing NULL would otherwise violate it while copying.
		not_null_defaults = {}
		for col in self.change_nullability:
			if col.not_nullable:
				default = get_not_null_defaults(col.fieldtype)
				not_null_defaults[col.fieldname] = (
					frappe.db.escape(default) if isinstance(default, str) else default
				)

		existing_columns = [col.split()[0] for col in existing_columns]
		select_exprs = [
			f"COALESCE({col}, {not_null_defaults[col.strip('`')]})"
			if col.strip("`") in not_null_defaults
			else col
			for col in existing_columns
		]
		frappe.db.sql_ddl(
			f"INSERT INTO `{temp_table}` ({', '.join(existing_columns)}) "
			f"SELECT {', '.join(select_exprs)} FROM `{self.table_name}`"
		)

		# Drop old table
		frappe.db.sql_ddl(f"DROP TABLE `{self.table_name}`")

		# Rename new table
		frappe.db.sql_ddl(f"ALTER TABLE `{temp_table}` RENAME TO `{self.table_name}`")

		# Replay the indexes that existed before the rebuild
		for index_sql in preserved_indexes:
			frappe.db.sql_ddl(index_sql)

		# Recreate indexes
		index_queries = []
		if self.add_unique:
			index_queries.extend(self.get_index_query(col.fieldname, unique=True) for col in self.add_unique)
		if self.add_index:
			index_queries.extend(
				self.get_index_query(col.fieldname)
				for col in self.add_index
				if not frappe.db.get_column_index(self.table_name, col.fieldname, unique=False)
			)
		if self.meta.sort_field == "modified" and not frappe.db.get_column_index(
			self.table_name, "modified", unique=False
		):
			index_queries.append(self.get_index_query("modified"))

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

	def index_name(self, fieldname: str, *, unique: bool = False) -> str:
		"""Build a database-unique index name for SQLite."""
		slug = re.sub(r"\W+", "_", self.table_name)
		suffix = "_unique" if unique else "_index"
		return f"{slug}_{fieldname}{suffix}"

	def get_index_query(self, fieldname: str, *, unique: bool = False) -> str:
		kind = "UNIQUE INDEX" if unique else "INDEX"
		return (
			f"CREATE {kind} IF NOT EXISTS `{self.index_name(fieldname, unique=unique)}` "
			f"ON `{self.table_name}`(`{fieldname}`)"
		)

	def get_column_index_queries(self) -> list[str]:
		queries = []
		for col in self.columns.values():
			if col.fieldname in frappe.db.DEFAULT_COLUMNS:
				continue
			if col.unique:
				queries.append(self.get_index_query(col.fieldname, unique=True))
			elif col.set_index:
				queries.append(self.get_index_query(col.fieldname))
		return queries

	def get_indexes_to_preserve(self) -> list[str]:
		"""Return user-defined indexes to recreate after a table rebuild."""
		drop_unique_fields = {col.fieldname for col in self.drop_unique}
		drop_index_fields = {col.fieldname for col in self.drop_index}

		statements = []
		for index in frappe.db.sql(
			"SELECT name, sql FROM sqlite_master WHERE type = 'index' AND tbl_name = %s AND sql IS NOT NULL",
			(self.table_name,),
			as_dict=True,
		):
			if drop_unique_fields or drop_index_fields:
				index_columns = {
					col["name"]
					for col in frappe.db.sql(
						"SELECT name FROM pragma_index_info(%s)",
						(index.name,),
						as_dict=True,
					)
				}
				is_unique = bool(re.match(r"^\s*CREATE\s+UNIQUE\s+INDEX", index.sql, flags=re.IGNORECASE))
				# Drop only the matching kind: toggling a column's uniqueness must not discard a
				# co-existing search index on the same field, and vice-versa.
				if is_unique and (index_columns & drop_unique_fields):
					continue
				if not is_unique and (index_columns & drop_index_fields):
					continue

			# Replays may overlap with add_index/add_unique.
			statement = re.sub(
				r"^\s*CREATE\s+(UNIQUE\s+)?INDEX\s+",
				lambda m: f"CREATE {m.group(1) or ''}INDEX IF NOT EXISTS ",
				index.sql,
				count=1,
				flags=re.IGNORECASE,
			)
			statements.append(statement)
		return statements
