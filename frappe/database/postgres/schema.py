import frappe
from frappe import _
from frappe.database.schema import DBTable, get_definition
from frappe.utils import cint, flt


class PostgresTable(DBTable):
	def create(self):
		add_text = ""

		# columns
		column_defs = self.get_column_definitions()
		if column_defs:
			add_text += ",\n".join(column_defs)

		# TODO: set docstatus length
		# create table
		frappe.db.sql(
			"""create table `%s` (
			name varchar({varchar_len}) not null primary key,
			creation timestamp(6),
			modified timestamp(6),
			modified_by varchar({varchar_len}),
			owner varchar({varchar_len}),
			docstatus smallint not null default '0',
			parent varchar({varchar_len}),
			parentfield varchar({varchar_len}),
			parenttype varchar({varchar_len}),
			idx bigint not null default '0',
			%s)""".format(
				varchar_len=frappe.db.VARCHAR_LEN
			)
			% (self.table_name, add_text)
		)

		self.create_indexes()
		frappe.db.commit()

	def create_indexes(self):
		create_index_query = ""
		for key, col in self.columns.items():
			if (
				col.set_index
				and col.fieldtype in frappe.db.type_map
				and frappe.db.type_map.get(col.fieldtype)[0] not in ("text", "longtext")
			):
				create_index_query += (
					'CREATE INDEX IF NOT EXISTS "{index_name}" ON `{table_name}`(`{field}`);'.format(
						index_name=col.fieldname, table_name=self.table_name, field=col.fieldname
					)
				)
		if create_index_query:
			# nosemgrep
			frappe.db.sql(create_index_query)

	def alter(self):
		for col in self.columns.values():
			col.build_for_alter_table(self.current_columns.get(col.fieldname.lower()))

		query = []

		for col in self.add_column:
			query.append("ADD COLUMN `{}` {}".format(col.fieldname, col.get_definition()))

		for col in self.change_type:
			using_clause = ""
			if col.fieldtype in ("Datetime"):
				# The USING option of SET DATA TYPE can actually specify any expression
				# involving the old values of the row
				# read more https://www.postgresql.org/docs/9.1/sql-altertable.html
				using_clause = "USING {}::timestamp without time zone".format(col.fieldname)
			elif col.fieldtype in ("Check"):
				using_clause = "USING {}::smallint".format(col.fieldname)

			query.append(
				"ALTER COLUMN `{0}` TYPE {1} {2}".format(
					col.fieldname,
					get_definition(col.fieldtype, precision=col.precision, length=col.length),
					using_clause,
				)
			)

		for col in self.set_default:
			if col.fieldname == "name":
				continue

			if col.fieldtype in ("Check", "Int"):
				col_default = cint(col.default)

			elif col.fieldtype in ("Currency", "Float", "Percent"):
				col_default = flt(col.default)

			elif not col.default:
				col_default = "NULL"

			else:
				col_default = "{}".format(frappe.db.escape(col.default))

			query.append("ALTER COLUMN `{}` SET DEFAULT {}".format(col.fieldname, col_default))

		create_contraint_query = ""
		for col in self.add_index:
			# if index key not exists
			create_contraint_query += (
				'CREATE INDEX IF NOT EXISTS "{index_name}" ON `{table_name}`(`{field}`);'.format(
					index_name=col.fieldname, table_name=self.table_name, field=col.fieldname
				)
			)

		for col in self.add_unique:
			# if index key not exists
			create_contraint_query += (
				'CREATE UNIQUE INDEX IF NOT EXISTS "unique_{index_name}" ON `{table_name}`(`{field}`);'.format(
					index_name=col.fieldname, table_name=self.table_name, field=col.fieldname
				)
			)

		drop_contraint_query = ""
		for col in self.drop_index:
			# primary key
			if col.fieldname != "name":
				# if index key exists
				drop_contraint_query += 'DROP INDEX IF EXISTS "{}" ;'.format(col.fieldname)

		for col in self.drop_unique:
			# primary key
			if col.fieldname != "name":
				# if index key exists
				drop_contraint_query += 'DROP INDEX IF EXISTS "unique_{}" ;'.format(col.fieldname)
		try:
			if query:
				final_alter_query = "ALTER TABLE `{}` {}".format(self.table_name, ", ".join(query))
				# nosemgrep
				frappe.db.sql(final_alter_query)
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
					_("{0} field cannot be set as unique in {1}, as there are non-unique existing values").format(
						fieldname, self.table_name
					)
				)
			else:
				raise e
