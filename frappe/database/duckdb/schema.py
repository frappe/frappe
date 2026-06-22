import frappe
from frappe.database.schema import DbColumn, DBTable, get_definition
from frappe.utils import cint, cstr, flt
from frappe.utils.defaults import get_not_null_defaults

NOT_NULL_TYPES = ("Check", "Int", "Currency", "Float", "Percent")


class DuckDBColumn(DbColumn):
	def get_definition(self, for_modification=False):
		column_def = get_definition(
			self.fieldtype,
			precision=self.precision,
			length=self.length,
			options=self.options,
			duckdb=True,
		)

		if not column_def:
			return column_def

		null = True
		default = None
		unique = False

		if self.fieldtype in NOT_NULL_TYPES:
			null = False

		if self.fieldtype in ("Check", "Int"):
			default = cint(self.default)

		elif self.fieldtype in ("Currency", "Float", "Percent"):
			default = flt(self.default)

		elif (
			self.default
			and (self.default not in frappe.db.DEFAULT_SHORTCUTS)
			and not cstr(self.default).startswith(":")
		):
			default = frappe.db.escape(self.default)

		if self.not_nullable and null:
			if default is None:
				default = get_not_null_defaults(self.fieldtype)
				if isinstance(default, str):
					default = frappe.db.escape(default)
			null = False

		if self.unique and not for_modification and (column_def not in ("text", "longtext")):
			unique = True

		if not null:
			column_def += " NOT NULL"

		if default is not None:
			column_def += f" DEFAULT {default}"

		if unique:
			column_def += " UNIQUE"
		return column_def


class DuckDBTable(DBTable):
	def is_new(self, conn):
		tables = [x[0] for x in conn.sql("show tables").fetchall()]
		return self.table_name not in tables

	def sync(self, conn):
		if self.meta.get("is_virtual"):
			# no schema to sync for virtual doctypes
			return
		if self.is_new(conn):
			self.create(conn)
		else:
			return

	def get_column_definitions(self):
		column_list = [*frappe.db.DEFAULT_COLUMNS]
		ret = []
		for k in list(self.columns):
			if k not in column_list:
				d = self.columns[k].get_definition()
				if d:
					ret.append('"' + k + '" ' + d)
					column_list.append(k)
		return ret

	def get_columns_from_docfields(self):
		"""
		get columns from docfields and custom fields
		"""
		fields = self.meta.get_fieldnames_with_value(with_field_meta=True)

		# optional fields like _comments
		if not self.meta.get("istable"):
			for fieldname in frappe.db.OPTIONAL_COLUMNS:
				fields.append({"fieldname": fieldname, "fieldtype": "Text"})

			# add _seen column if track_seen
			if self.meta.get("track_seen"):
				fields.append({"fieldname": "_seen", "fieldtype": "Text"})

		# amended_from
		fields.append({"fieldname": "amended_from", "fieldtype": "Data"})
		for field in fields:
			if field.get("is_virtual"):
				continue

			self.columns[field.get("fieldname")] = DuckDBColumn(
				table=self,
				fieldname=field.get("fieldname"),
				fieldtype=field.get("fieldtype"),
				length=field.get("length"),
				default=field.get("default"),
				set_index=field.get("search_index"),
				options=field.get("options"),
				unique=field.get("unique"),
				precision=field.get("precision"),
				not_nullable=field.get("not_nullable"),
			)

	def create(self, conn):
		additional_definitions = []
		varchar_len = frappe.db.VARCHAR_LEN
		name_column = f"name varchar({varchar_len}) primary key"

		# columns
		column_defs = self.get_column_definitions()
		if column_defs:
			additional_definitions += column_defs

		# child table columns
		if self.meta.get("istable", default=0):
			additional_definitions += [
				f"parent varchar({varchar_len})",
				f"parentfield varchar({varchar_len})",
				f"parenttype varchar({varchar_len})",
			]
		additional_definitions = ",\n".join(additional_definitions)

		# create table
		query = f"""create table \"{self.table_name}\" (
			{name_column},
			creation datetime(6),
			modified datetime(6),
			modified_by varchar({varchar_len}),
			owner varchar({varchar_len}),
			docstatus tinyint not null default '0',
			idx int not null default '0',
			{additional_definitions})
			"""

		conn.sql(query)
