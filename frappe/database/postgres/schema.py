import frappe
from frappe import _
from frappe.utils import cint, flt
from frappe.database.schema import DBTable, get_definition

# FIXME: Should `tabDefaultValue` be site specific?
# List of site specific tables (Does not maintain tenant information)
SITE_SPECIFIC_TABLES = ['tabProperty Setter', 'tabCustom Field', 'tabDefaultValue', 'tabModule Def', 'tabLanguage']

class PostgresTable(DBTable):
	def create(self):
		if self.table_name in SITE_SPECIFIC_TABLES:
			self.create_table()
		else:
			self.create_table_multitenant()

	def create_table(self):
		"""Create a table that is common to all the tenants in the site.
		"""
		# Get doctype columns and constraints
		column_defs = self.get_column_definitions()
		constraints = self.get_constraint_definitions()

		generated_schema = ',\n'.join(column_defs + constraints)

		# index
		# index_defs = self.get_index_definitions()
		# TODO: set docstatus length
		# create table
		sql = """create table `%s` (
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
			%s)""".format(varchar_len=frappe.db.VARCHAR_LEN) % (self.table_name, generated_schema)

		frappe.db.sql(sql.strip(',\n'))
		frappe.db.commit()

	def create_table_multitenant(self):
		"""Create a table that maintains tenant wise data.
		"""
		# Get doctype columns and constraints
		column_defs = self.get_column_definitions()
		default_constraints = ["PRIMARY KEY (`tenant_id`, `name`)"]
		constraints =  default_constraints + self.get_constraint_definitions()

		generated_schema = ',\n'.join(column_defs + constraints)

		# index
		# index_defs = self.get_index_definitions()
		# TODO: set docstatus length

		# create table
		sql = """create table `%s` (
			name varchar({varchar_len}) not null,
			tenant_id integer not null DEFAULT current_setting('app.current_tenant')::integer,
			creation timestamp(6),
			modified timestamp(6),
			modified_by varchar({varchar_len}),
			owner varchar({varchar_len}),
			docstatus smallint not null default '0',
			parent varchar({varchar_len}),
			parentfield varchar({varchar_len}),
			parenttype varchar({varchar_len}),
			idx bigint not null default '0',
			%s)""".format(varchar_len=frappe.db.VARCHAR_LEN) % (self.table_name, generated_schema)

		frappe.db.sql(sql.strip(',\n'))
		frappe.db.sql(
			"ALTER TABLE `%s` ENABLE ROW LEVEL SECURITY;" % (self.table_name))
		frappe.db.sql(
			"ALTER TABLE `%s` FORCE ROW LEVEL SECURITY;" % (self.table_name))

		frappe.db.sql("""CREATE POLICY `%s_isolation_policy` ON `%s`
			USING (tenant_id = current_setting('app.current_tenant')::integer);
			""" % (self.table_name, self.table_name))

		frappe.db.commit()

	def get_constraint_definitions(self):
		"""Generate column level constraints of a table.
		"""
		constaints = []
		for key, col in self.columns.items():
			if col.unique:
				if self.table_name in SITE_SPECIFIC_TABLES:
					constaints.append(f'UNIQUE (`{key}`)')
				else:
					constaints.append(f'UNIQUE (`tenant_id`, `{key}`)')
		return constaints

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

			query.append("ALTER COLUMN `{0}` TYPE {1} {2}".format(
				col.fieldname,
				get_definition(col.fieldtype, precision=col.precision, length=col.length),
				using_clause)
			)

		for col in self.set_default:
			if col.fieldname=="name":
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

		create_index_query = ""
		for col in self.add_index:
			# if index key not exists
			create_index_query += 'CREATE INDEX IF NOT EXISTS "{index_name}" ON `{table_name}`(`{field}`);'.format(
				index_name=col.fieldname,
				table_name=self.table_name,
				field=col.fieldname)

		drop_index_query = ""
		for col in self.drop_index:
			# primary key
			if col.fieldname != 'name':
				# if index key exists
				if not frappe.db.has_index(self.table_name, col.fieldname):
					drop_index_query += 'DROP INDEX IF EXISTS "{}" ;'.format(col.fieldname)

		if query:
			try:
				final_alter_query = "ALTER TABLE `{}` {}".format(self.table_name, ", ".join(query))
				if final_alter_query: frappe.db.sql(final_alter_query)
				if create_index_query: frappe.db.sql(create_index_query)
				if drop_index_query: frappe.db.sql(drop_index_query)
			except Exception as e:
				# sanitize
				if frappe.db.is_duplicate_fieldname(e):
					frappe.throw(str(e))
				elif frappe.db.is_duplicate_entry(e):
					fieldname = str(e).split("'")[-2]
					frappe.throw(_("""{0} field cannot be set as unique in {1},
						as there are non-unique existing values""").format(
						fieldname, self.table_name))
					raise e
				else:
					raise e
