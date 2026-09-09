import frappe
from frappe import _
from frappe.database.schema import DBTable, get_definition
from frappe.utils import cint, flt
from frappe.utils.defaults import get_not_null_defaults


def get_type_affinity(declared_type: str) -> str:
	"""Return the storage affinity SQLite assigns to a declared type."""
	declared_type = declared_type.upper()
	if "INT" in declared_type:
		return "integer"
	if any(token in declared_type for token in ("CHAR", "CLOB", "TEXT")):
		return "text"
	if "BLOB" in declared_type or not declared_type:
		return "blob"
	if any(token in declared_type for token in ("REAL", "FLOA", "DOUB")):
		return "real"
	return "numeric"


def types_are_compatible(current_type: str, target_type: str) -> bool:
	"""Return whether two declarations are safe to treat as the same SQLite type.

	Only known legacy aliases are accepted here. Length changes such as varchar(140) to varchar(255) remain real schema changes.
	"""
	current_type = current_type.strip().lower()
	target_type = target_type.strip().lower()
	if current_type == target_type:
		return True

	current_base = current_type.partition("(")[0].strip()
	target_base = target_type.partition("(")[0].strip()
	aliases = frozenset((current_base, target_base))
	return aliases in (
		frozenset(("text", "varchar")),
		frozenset(("datetime", "timestamp")),
	) and get_type_affinity(current_type) == get_type_affinity(target_type)


class SQLiteTable(DBTable):
	def create(self):
		additional_definitions = []
		varchar_len = frappe.db.VARCHAR_LEN
		name_column = f"name varchar({varchar_len}) PRIMARY KEY"

		# columns
		column_defs = self.get_column_definitions()
		if column_defs:
			additional_definitions += column_defs

		index_defs = []
		for fieldname, column in self.columns.items():
			column_type = frappe.db.type_map.get(column.fieldtype, (None,))[0]
			if column.set_index and not column.unique and column_type not in (None, "text", "longtext"):
				index_defs.append(
					f"CREATE INDEX `{self.table_name}_{fieldname}_index` "
					f"ON `{self.table_name}` (`{fieldname}`)"
				)

		# child table columns
		if self.meta.get("istable", default=0):
			additional_definitions.extend(
				[
					f"parent varchar({varchar_len})",
					f"parentfield varchar({varchar_len})",
					f"parenttype varchar({varchar_len})",
				]
			)
			index_defs.append(
				f"CREATE INDEX `{self.table_name}_parent_idx` ON `{self.table_name}` (`parent`)"
			)
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
			name_column = "name uuid PRIMARY KEY"

		definitions = ",\n".join(
			[
				name_column,
				"creation timestamp",
				"modified timestamp",
				f"modified_by varchar({varchar_len})",
				f"owner varchar({varchar_len})",
				"docstatus INTEGER NOT NULL DEFAULT 0",
				"idx INTEGER NOT NULL DEFAULT 0",
				*additional_definitions,
			]
		)
		create_table_query = f"CREATE TABLE `{self.table_name}` (\n{definitions}\n)"

		# Execute table creation
		frappe.db.sql_ddl(create_table_query)

		# Create indexes separately
		for index_query in index_defs:
			frappe.db.sql_ddl(index_query)

	def alter(self):
		from frappe.database.sqlite.database import get_column_definition, rebuild_table

		for col in self.columns.values():
			current_definition = self.current_columns.get(col.fieldname.lower())
			if current_definition:
				target_type = get_definition(
					col.fieldtype,
					precision=col.precision,
					length=col.length,
					options=col.options,
				)
				if target_type and types_are_compatible(current_definition.type, target_type):
					current_definition = frappe._dict(current_definition.copy())
					current_definition.type = target_type
			col.build_for_alter_table(current_definition)

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

		for col in self.change_type:
			self.validate_type_change(col)

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
		for col in self.change_type:
			if col.fieldtype not in frappe.model.numeric_fieldtypes:
				continue
			default = col.default or get_not_null_defaults(col.fieldtype)
			default = cint(default) if col.fieldtype in ("Check", "Int", "Long Int") else flt(default)
			pre_rebuild_queries.append(
				f"UPDATE `{self.table_name}` SET `{col.fieldname}` = {default} "
				f"WHERE `{col.fieldname}` IS NOT NULL "
				f"AND TRIM(CAST(`{col.fieldname}` AS TEXT)) = ''"
			)
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

	def validate_type_change(self, column) -> None:
		"""Reject values SQLite cannot safely store as the requested numeric type."""
		if column.fieldtype not in frappe.model.numeric_fieldtypes:
			return

		value = f"TRIM(CAST(`{column.fieldname}` AS TEXT))"
		if column.fieldtype in ("Int", "Long Int", "Check"):
			pattern = r"^[+-]?[0-9]+$"
		else:
			pattern = r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$"

		invalid = frappe.db.sql(
			f"""SELECT 1 FROM `{self.table_name}`
			WHERE `{column.fieldname}` IS NOT NULL
				AND {value} != ''
				AND regexp(%s, {value}) = 0
			LIMIT 1""",
			(pattern,),
			_skip_sqlite_transpilation=True,
		)

		if not invalid and column.fieldtype in ("Int", "Long Int"):
			is_bigint = column.fieldtype == "Long Int" or (column.length and column.length > 11)
			positive_limit = "9223372036854775807" if is_bigint else "2147483647"
			negative_limit = "9223372036854775808" if is_bigint else "2147483648"
			magnitude = f"LTRIM(LTRIM({value}, '+-'), '0')"
			invalid = frappe.db.sql(
				f"""SELECT 1 FROM `{self.table_name}`
				WHERE `{column.fieldname}` IS NOT NULL
					AND {value} != ''
					AND (
						(SUBSTR({value}, 1, 1) = '-' AND (
							LENGTH({magnitude}) > {len(negative_limit)}
							OR (LENGTH({magnitude}) = {len(negative_limit)} AND {magnitude} > %s)
						))
						OR (SUBSTR({value}, 1, 1) != '-' AND (
							LENGTH({magnitude}) > {len(positive_limit)}
							OR (LENGTH({magnitude}) = {len(positive_limit)} AND {magnitude} > %s)
						))
					)
				LIMIT 1""",
				(negative_limit, positive_limit),
				_skip_sqlite_transpilation=True,
			)

		if not invalid and column.fieldtype in ("Currency", "Float", "Percent"):
			exponent_position = f"INSTR(LOWER({value}), 'e')"
			mantissa = (
				f"CASE WHEN {exponent_position} > 0 "
				f"THEN SUBSTR({value}, 1, {exponent_position} - 1) ELSE {value} END"
			)
			invalid = frappe.db.sql(
				f"""SELECT 1 FROM `{self.table_name}`
				WHERE `{column.fieldname}` IS NOT NULL
					AND {value} != ''
					AND (
						ABS(CAST({value} AS REAL)) >= 9e999
						OR (CAST({value} AS REAL) = 0 AND regexp('[1-9]', {mantissa}) = 1)
					)
				LIMIT 1""",
				_skip_sqlite_transpilation=True,
			)

		if invalid:
			frappe.throw(
				_(
					"Cannot change field type in {0}: some existing values cannot be converted to the new type"
				).format(self.doctype)
			)
