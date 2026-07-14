import hashlib

import frappe
from frappe import _
from frappe.database.schema import DbColumn, DBTable, get_definition
from frappe.utils import cint, flt
from frappe.utils.defaults import get_not_null_defaults


# PostgreSQL index names are unique per *schema*, not per table like MariaDB. Naming an index
# after just its field(s) therefore collides across tables that share a field (item_code,
# company, posting_date, lft/rgt, ...) and `CREATE INDEX IF NOT EXISTS` silently skips all but
# the first -- so most tables never get that index. Qualify the name with the table so it is
# schema-unique, hashing if it would exceed postgres's 63-byte identifier cap.
def get_qualified_index_name(table_name: str, fields: list[str], suffix: str | None = None) -> str:
	base = f"{table_name}_" + "_".join(fields)
	if suffix:
		base += f"_{suffix}"
	name = f"{base}_index"
	if len(name.encode()) > 63:
		digest = hashlib.md5(base.encode()).hexdigest()[:10]
		name = f"{name[:52]}_{digest}"
	return name


def get_single_column_index_name(table_name: str, fieldname: str) -> str:
	return get_qualified_index_name(table_name, [fieldname])


class PostgresTable(DBTable):
	def create(self):
		varchar_len = frappe.db.VARCHAR_LEN
		name_column = f"name varchar({varchar_len}) primary key"

		additional_definitions = ""
		# columns
		column_defs = self.get_column_definitions()
		if column_defs:
			additional_definitions += ",\n".join(column_defs)

		# child table columns
		if self.meta.get("istable", default=0):
			if column_defs:
				additional_definitions += ",\n"

			additional_definitions += ",\n".join(
				(
					f"parent varchar({varchar_len})",
					f"parentfield varchar({varchar_len})",
					f"parenttype varchar({varchar_len})",
				)
			)

		# creating sequence(s)
		if not self.meta.issingle and self.meta.autoname == "autoincrement":
			frappe.db.create_sequence(self.doctype, check_not_exists=True)
			name_column = "name bigint primary key"

		elif not self.meta.issingle and self.meta.autoname == "UUID":
			name_column = "name uuid primary key"

		# TODO: set docstatus length
		# create table
		frappe.db.sql(
			f"""create table `{self.table_name}` (
			{name_column},
			creation timestamp(6),
			modified timestamp(6),
			modified_by varchar({varchar_len}),
			owner varchar({varchar_len}),
			docstatus smallint not null default '0',
			idx bigint not null default '0',
			{additional_definitions}
			)""",
		)

		self.create_indexes()
		frappe.db.commit()

	def create_indexes(self):
		create_index_query = ""
		for col in self.columns.values():
			if (
				col.set_index
				and col.fieldtype in frappe.db.type_map
				and frappe.db.type_map.get(col.fieldtype)[0] not in ("text", "longtext")
			):
				index_name = get_single_column_index_name(self.table_name, col.fieldname)
				create_index_query += (
					f'CREATE INDEX IF NOT EXISTS "{index_name}" ON `{self.table_name}`(`{col.fieldname}`);'
				)
		if create_index_query:
			# nosemgrep
			frappe.db.sql(create_index_query)

	def alter(self):
		for col in self.columns.values():
			col.build_for_alter_table(self.current_columns.get(col.fieldname.lower()))

		query = [f"ADD COLUMN `{col.fieldname}` {col.get_definition()}" for col in self.add_column]

		new_column_names = {col.fieldname for col in self.add_column}

		for col in self.change_type:
			# Postgres won't implicitly cast text/varchar to these types, so SET DATA TYPE
			# needs an explicit USING expression. NOT NULL numerics coalesce blanks to 0;
			# nullable types map blanks to NULL.
			using_clause = ""
			if col.fieldtype == "Datetime":
				using_clause = f"USING NULLIF(`{col.fieldname}`::text, '')::timestamp without time zone"
			elif col.fieldtype == "Date":
				using_clause = f"USING NULLIF(`{col.fieldname}`::text, '')::date"
			elif col.fieldtype == "Time":
				using_clause = f"USING NULLIF(`{col.fieldname}`::text, '')::time without time zone"
			elif col.fieldtype == "Check":
				using_clause = f"USING COALESCE(NULLIF(`{col.fieldname}`::text, ''), '0')::smallint"
			elif col.fieldtype in ("Currency", "Float", "Percent"):
				using_clause = f"USING COALESCE(NULLIF(`{col.fieldname}`::text, ''), '0')::numeric"
			elif col.fieldtype in ("Duration", "Rating"):
				# Duration/Rating are nullable (not in NOT_NULL_TYPES), so keep blanks NULL.
				using_clause = f"USING NULLIF(`{col.fieldname}`::text, '')::numeric"
			elif col.fieldtype == "Int":
				# cast to the actual target type: Int with length > 11 is a bigint column
				# (Long Int), so a plain ::int would overflow its legitimate values; a standard
				# Int stays int and still errors on out-of-range values (use Long Int for those).
				int_type = get_definition(col.fieldtype, length=col.length)
				using_clause = (
					f"USING COALESCE(NULLIF(`{col.fieldname}`::text, ''), '0')::numeric::{int_type}"
				)
			elif col.fieldtype == "JSON":
				using_clause = f"USING NULLIF(`{col.fieldname}`::text, '')::json"

			if using_clause:
				# the column's existing (string) DEFAULT can't be cast to the new type, so
				# drop it and re-apply the proper default via the set_default pass below.
				query.append(f"ALTER COLUMN `{col.fieldname}` DROP DEFAULT")
				if col not in self.set_default:
					self.set_default.append(col)

			query.append(
				"ALTER COLUMN `{}` TYPE {} {}".format(
					col.fieldname,
					get_definition(col.fieldtype, precision=col.precision, length=col.length),
					using_clause,
				)
			)

		if alter_pk := self.alter_primary_key():
			query.append(alter_pk)

		for col in self.set_default:
			if col.fieldname == "name":
				continue

			if col.fieldtype in ("Check", "Int"):
				col_default = cint(col.default)

			elif col.fieldtype in ("Currency", "Float", "Percent"):
				col_default = flt(col.default)

			elif not col.default:
				# nullable types (e.g. Duration, Rating) keep their NULL default
				col_default = "NULL"

			else:
				col_default = f"{frappe.db.escape(col.default)}"

			query.append(f"ALTER COLUMN `{col.fieldname}` SET DEFAULT {col_default}")

		create_contraint_query = ""
		for col in self.add_index:
			# if index key not exists
			index_name = get_single_column_index_name(self.table_name, col.fieldname)
			create_contraint_query += (
				f'CREATE INDEX IF NOT EXISTS "{index_name}" ON `{self.table_name}`(`{col.fieldname}`);'
			)

		for col in self.add_unique:
			# if index key not exists
			if col.fieldname not in new_column_names:
				create_contraint_query += 'CREATE UNIQUE INDEX IF NOT EXISTS "unique_{index_name}" ON `{table_name}`(`{field}`);'.format(
					index_name=col.fieldname, table_name=self.table_name, field=col.fieldname
				)

		# logic to drop unique constraint for fields deleted from a doctype
		meta_columns = set(self.columns.keys())
		db_columns = set(self.current_columns.keys())

		for col in db_columns:
			if (
				col not in meta_columns
				and col not in frappe.db.DEFAULT_COLUMNS
				and col not in frappe.db.OPTIONAL_COLUMNS
			):
				has_unique_index = frappe.db.sql(
					"""
					SELECT 1
					FROM pg_indexes
					WHERE tablename = %s
					AND indexname IN (%s, %s)
					LIMIT 1
					""",
					(
						self.table_name,
						f"{self.table_name}_{col}_key",
						f"unique_{col}",
					),
				)

				if not has_unique_index:
					continue

				current_col = self.current_columns.get(col)

				deleted_col = DbColumn(
					table=self,
					fieldname=current_col.name,
					fieldtype=current_col.type,
					length=None,
					default=None,
					set_index=current_col.index,
					options=None,
					unique=False,
					precision=None,
					not_nullable=current_col.not_nullable,
				)
				self.drop_unique.append(deleted_col)

		drop_contraint_query = ""
		for col in self.drop_index:
			# primary key
			if col.fieldname != "name":
				# if index key exists; use the schema-unique name (a bare-fieldname DROP would be
				# schema-global on postgres and could drop another table's like-named index)
				index_name = get_single_column_index_name(self.table_name, col.fieldname)
				drop_contraint_query += f'DROP INDEX IF EXISTS "{index_name}" ;'

		for col in self.drop_unique:
			# primary key
			if col.fieldname != "name":
				# drop unique constraint first if exists which automatically drops the underlying index also
				unique_constraint_exists = frappe.db.sql(
					"""
					SELECT 1
					FROM pg_constraint
					WHERE conname = %s
					""",
					(f"{self.table_name}_{col.fieldname}_key",),
				)

				if unique_constraint_exists:
					drop_contraint_query += f'ALTER TABLE "{self.table_name}" DROP CONSTRAINT IF EXISTS "{self.table_name}_{col.fieldname}_key" ;'

				# drop the unique index backed by no constraint directly
				unique_index_exists = frappe.db.sql(
					"""
					SELECT 1
					FROM pg_indexes
					WHERE tablename = %s
					AND indexname = %s
					""",
					(
						self.table_name,
						f"unique_{col.fieldname}",
					),
				)

				if unique_index_exists:
					drop_contraint_query += f'DROP INDEX IF EXISTS "unique_{col.fieldname}" ;'

		change_nullability = []
		for col in self.change_nullability:
			default = col.default or get_not_null_defaults(col.fieldtype)
			if isinstance(default, str):
				default = frappe.db.escape(default)
			change_nullability.append(
				f'ALTER COLUMN "{col.fieldname}" {"SET" if col.not_nullable else "DROP"} NOT NULL'
			)
			change_nullability.append(f'ALTER COLUMN "{col.fieldname}" SET DEFAULT {default}')

			if col.not_nullable:
				try:
					table = frappe.qb.DocType(self.doctype)
					frappe.qb.update(table).set(
						col.fieldname, col.default or get_not_null_defaults(col.fieldtype)
					).where(table[col.fieldname].isnull()).run()
				except Exception:
					print(f"Failed to update data in {self.table_name} for {col.fieldname}")
					raise
		try:
			if query:
				final_alter_query = "ALTER TABLE `{}` {}".format(self.table_name, ", ".join(query))
				# nosemgrep
				frappe.db.sql(final_alter_query)
			if change_nullability:
				# nosemgrep
				frappe.db.sql(f"ALTER TABLE `{self.table_name}` {','.join(change_nullability)}")
			if create_contraint_query:
				# nosemgrep
				frappe.db.sql(create_contraint_query)
			if drop_contraint_query:
				# nosemgrep
				frappe.db.sql(drop_contraint_query)
		except Exception as e:
			# sanitize
			if frappe.db.is_duplicate_fieldname(e):
				frappe.throw(str(e))
			elif frappe.db.is_duplicate_entry(e):
				fieldname = str(e).split("'")[-2]
				frappe.throw(
					_(
						"{0} field cannot be set as unique in {1}, as there are non-unique existing values"
					).format(fieldname, self.table_name)
				)
			elif frappe.db.is_data_truncated(e):
				frappe.throw(
					_(
						"Cannot change field type in {0}: some existing values cannot be converted to the new type"
					).format(self.doctype),
					title=_("Incompatible Values"),
				)
			else:
				raise e

	def alter_primary_key(self) -> str | None:
		# If there are no values in table allow migrating to UUID from varchar
		autoname = self.meta.autoname
		if autoname == "UUID" and frappe.db.get_column_type(self.doctype, "name") != "uuid":
			if not frappe.db.get_value(self.doctype, {}, order_by=None):
				return "alter column `name` TYPE uuid USING name::uuid"
			else:
				frappe.throw(
					_("Primary key of doctype {0} can not be changed as there are existing values.").format(
						self.doctype
					)
				)

		# Reverting from UUID to VARCHAR
		if autoname != "UUID" and frappe.db.get_column_type(self.doctype, "name") == "uuid":
			return f"alter column `name` TYPE varchar({frappe.db.VARCHAR_LEN})"
