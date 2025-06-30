import re

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt
from frappe.utils.defaults import get_not_null_defaults

# This matches anything that isn't [a-zA-Z0-9_]
SPECIAL_CHAR_PATTERN = re.compile(r"[\W]", flags=re.UNICODE)

VARCHAR_CAST_PATTERN = re.compile(r"varchar\(([\d]+)\)")


class InvalidColumnName(frappe.ValidationError):
	pass


class DBTable:
	def __init__(self, doctype, meta=None):
		self.doctype = doctype
		self.table_name = f"tab{doctype}"
		self.meta = meta or frappe.get_meta(doctype, False)
		self.columns: dict[str, DbColumn] = {}
		self.current_columns = {}

		# lists for change
		self.add_column: list[DbColumn] = []
		self.change_type: list[DbColumn] = []
		self.change_name: list[DbColumn] = []
		self.change_nullability: list[DbColumn] = []
		self.add_unique: list[DbColumn] = []
		self.add_index: list[DbColumn] = []
		self.drop_unique: list[DbColumn] = []
		self.drop_index: list[DbColumn] = []
		self.set_default: list[DbColumn] = []

		# load
		self.get_columns_from_docfields()

	def sync(self):
		if self.meta.get("is_virtual"):
			# no schema to sync for virtual doctypes
			return
		if self.is_new():
			self.create()
		else:
			frappe.client_cache.delete_value(f"table_columns::{self.table_name}")
			self.alter()

	def create(self):
		pass

	def get_column_definitions(self):
		column_list = [*frappe.db.DEFAULT_COLUMNS]
		ret = []
		for k in list(self.columns):
			if k not in column_list:
				d = self.columns[k].get_definition()
				if d:
					ret.append("`" + k + "` " + d)
					column_list.append(k)
		return ret

	def get_index_definitions(self):
		return [
			"index `" + key + "`(`" + key + "`)"
			for key, col in self.columns.items()
			if (
				col.set_index
				and not col.unique
				and col.fieldtype in frappe.db.type_map
				and frappe.db.type_map.get(col.fieldtype)[0] not in ("text", "longtext")
			)
		]

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

		for field in fields:
			if field.get("is_virtual"):
				continue

			self.columns[field.get("fieldname")] = DbColumn(
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

	def validate(self):
		"""Check if change in varchar length isn't truncating the columns"""
		if self.is_new():
			return

		self.setup_table_columns()

		columns = [
			frappe._dict({"fieldname": f, "fieldtype": "Data"}) for f in frappe.db.STANDARD_VARCHAR_COLUMNS
		]
		if self.meta.get("istable"):
			columns += [
				frappe._dict({"fieldname": f, "fieldtype": "Data"}) for f in frappe.db.CHILD_TABLE_COLUMNS
			]
		columns += self.columns.values()

		for col in columns:
			if len(col.fieldname) >= 64:
				frappe.throw(
					_("Fieldname is limited to 64 characters ({0})").format(frappe.bold(col.fieldname))
				)

			if "varchar" in frappe.db.type_map.get(col.fieldtype, ()):
				# validate length range
				new_length = cint(col.length) or cint(frappe.db.VARCHAR_LEN)
				if not (1 <= new_length <= 1000):
					frappe.throw(_("Length of {0} should be between 1 and 1000").format(col.fieldname))

				current_col = self.current_columns.get(col.fieldname, {})
				if not current_col:
					continue
				current_type = self.current_columns[col.fieldname]["type"]
				current_length = VARCHAR_CAST_PATTERN.findall(current_type)
				if not current_length:
					# case when the field is no longer a varchar
					continue
				current_length = current_length[0]
				if cint(current_length) != cint(new_length):
					try:
						# check for truncation
						max_length = frappe.db.sql(
							f"""SELECT MAX(CHAR_LENGTH(`{col.fieldname}`)) FROM `tab{self.doctype}`"""
						)

					except frappe.db.InternalError as e:
						if frappe.db.is_missing_column(e):
							# Unknown column 'column_name' in 'field list'
							continue
						raise

					if max_length and max_length[0][0] and max_length[0][0] > new_length:
						if col.fieldname in self.columns:
							self.columns[col.fieldname].length = current_length
						info_message = _(
							"Reverting length to {0} for '{1}' in '{2}'. Setting the length as {3} will cause truncation of data."
						).format(current_length, col.fieldname, self.doctype, new_length)
						frappe.msgprint(info_message)

	def is_new(self):
		return self.table_name not in frappe.db.get_tables()

	def setup_table_columns(self):
		# TODO: figure out a way to get key data
		for c in frappe.db.get_table_columns_description(self.table_name):
			self.current_columns[c.name.lower()] = c

	def alter(self):
		pass


NOT_NULL_TYPES = ("Check", "Int", "Currency", "Float", "Percent")


class DbColumn:
	def __init__(
		self,
		*,
		table,
		fieldname,
		fieldtype,
		length,
		default,
		set_index,
		options,
		unique,
		precision,
		not_nullable,
	):
		self.table = table
		self.fieldname = fieldname
		self.fieldtype = fieldtype
		self.length = length
		self.set_index = set_index
		self.default = default
		self.options = options
		self.unique = unique
		self.precision = precision
		self.not_nullable = not_nullable

	def get_definition(self, for_modification=False):
		column_def = get_definition(
			self.fieldtype,
			precision=self.precision,
			length=self.length,
			options=self.options,
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

	def build_for_alter_table(self, current_def):
		column_type = get_definition(self.fieldtype, self.precision, self.length)

		# no columns
		if not column_type:
			return

		# to add?
		if not current_def:
			self.fieldname = validate_column_name(self.fieldname)
			self.table.add_column.append(self)

			if column_type not in ("text", "longtext"):
				if self.unique:
					self.table.add_unique.append(self)
				if self.set_index:
					self.table.add_index.append(self)
			return

		# type
		if current_def["type"] != column_type and not (
			# XXX: MariaDB JSON is same as longtext and information schema still returns longtext
			current_def["type"] == "longtext" and column_type == "json" and frappe.db.db_type == "mariadb"
		):
			self.table.change_type.append(self)

		# unique
		if (self.unique and not current_def.get("unique")) and column_type not in ("text", "longtext"):
			self.table.add_unique.append(self)
		elif (current_def.get("unique") and not self.unique) and column_type not in ("text", "longtext"):
			self.table.drop_unique.append(self)

		# default
		if (
			self.default_changed(current_def)
			and (self.default not in frappe.db.DEFAULT_SHORTCUTS)
			and not cstr(self.default).startswith(":")
		):
			self.table.set_default.append(self)

		# nullability
		if (
			self.not_nullable is not None
			and (self.not_nullable != current_def.get("not_nullable"))
			and self.fieldtype not in NOT_NULL_TYPES
		):
			self.table.change_nullability.append(self)

		# index should be applied or dropped irrespective of type change
		if (current_def.get("index") and not self.set_index) and column_type not in ("text", "longtext"):
			self.table.drop_index.append(self)

		elif (not current_def.get("index") and self.set_index) and column_type not in ("text", "longtext"):
			self.table.add_index.append(self)

	def default_changed(self, current_def):
		if "decimal" in current_def["type"]:
			return self.default_changed_for_decimal(current_def)
		else:
			cur_default = current_def.get("default")
			new_default = self.default
			if cur_default == "NULL":
				cur_default = None
			else:
				# Strip quotes from default value
				# eg. database returns default value as "'System Manager'"
				cur_default = cur_default.lstrip("'").rstrip("'").replace("\\\\", "\\")

			fieldtype = self.fieldtype
			db_field_type = frappe.db.type_map.get(fieldtype)
			if fieldtype in ["Int", "Check"]:
				cur_default = cint(cur_default)
				new_default = cint(new_default)
			elif fieldtype in ["Currency", "Float", "Percent"]:
				cur_default = flt(cur_default)
				new_default = flt(new_default)
			elif fieldtype == "Time":
				return self.default_changed_for_time(cur_default, new_default)
			elif db_field_type and db_field_type[0] in ("varchar", "longtext", "text"):
				new_default = cstr(new_default)
				if not current_def.get("not_nullable"):
					cur_default = cstr(cur_default)
			return cur_default != new_default

	def default_changed_for_decimal(self, current_def):
		cur_default = current_def["default"]
		if cur_default == "NULL":
			cur_default = None
		try:
			if cur_default in ("", None) and self.default in ("", None):
				return False

			elif flt(cur_default) == 0.0 and flt(self.default) == 0.0:
				return False

			elif cur_default in ("", None):
				try:
					# check if new default value is valid
					float(self.default)
					return True
				except ValueError:
					return False

			elif self.default in ("", None):
				# new default value is empty
				return True

			else:
				# NOTE float() raise ValueError when "" or None is passed
				return float(cur_default) != float(self.default)
		except TypeError:
			return True

	def default_changed_for_time(self, cur_default: str, new_default: str):
		from datetime import datetime

		# Normalize time values to HH:MM:SS.ssssss format, from formats: HH:MM:SS.ssssss, HH:MM:SS, HH:MM
		def normalize_time(val):
			if not val:
				return None
			for fmt in ("%H:%M:%S.%f", "%H:%M:%S", "%H:%M"):
				try:
					return datetime.strptime(val, fmt).time().strftime("%H:%M:%S.%f")
				except ValueError:
					continue
			return val

		cur = normalize_time(cur_default)
		new = normalize_time(new_default)
		return cur != new


def validate_column_name(n):
	if special_characters := SPECIAL_CHAR_PATTERN.findall(n):
		special_characters = ", ".join(f'"{c}"' for c in special_characters)
		frappe.throw(
			_("Fieldname {0} cannot have special characters like {1}").format(
				frappe.bold(cstr(n)), special_characters
			),
			frappe.db.InvalidColumnName,
		)
	return n


def validate_column_length(fieldname):
	if len(fieldname) > frappe.db.MAX_COLUMN_LENGTH:
		frappe.throw(_("Fieldname is limited to 64 characters ({0})").format(fieldname))


def get_definition(fieldtype, precision=None, length=None, *, options=None):
	d = frappe.db.type_map.get(fieldtype)

	if (
		fieldtype == "Link"
		and options
		# XXX: This might not trigger if referred doctype is not yet created
		# This is largely limitation of how migration happens though.
		# Maybe we can sort by creation and then modified?
		and frappe.db.exists("DocType", options)
		and frappe.get_meta(options).autoname == "UUID"
	):
		d = ("uuid", None)

	if not d:
		return

	if fieldtype == "Int" and length and length > 11:
		# convert int to long int if the length of the int is greater than 11
		d = frappe.db.type_map.get("Long Int")

	coltype = d[0]
	size = d[1] if d[1] else None

	if size:
		# This check needs to exist for backward compatibility.
		# Till V13, default size used for float, currency and percent are (18, 6).
		if fieldtype in ["Float", "Currency", "Percent"] and cint(precision) > 6:
			size = "21,9"

		if length:
			if coltype == "varchar":
				size = length
			elif coltype == "int" and length < 11:
				# allow setting custom length for int if length provided is less than 11
				# NOTE: this will only be applicable for mariadb as frappe implements int
				# in postgres as bigint (as seen in type_map)
				size = length

	if size is not None:
		coltype = f"{coltype}({size})"

	return coltype


def add_column(doctype, column_name, fieldtype, precision=None, length=None, default=None, not_null=False):
	frappe.db.commit()
	if frappe.db.db_type == "sqlite":
		if column_name in frappe.db.get_table_columns(doctype):
			return
		query = "alter table `tab{}` add column {} {}".format(
			doctype,
			column_name,
			get_definition(fieldtype, precision, length),
		)
	else:
		query = "alter table `tab{}` add column if not exists {} {}".format(
			doctype,
			column_name,
			get_definition(fieldtype, precision, length),
		)

	if not_null:
		query += " not null"
	if default:
		query += f" default '{default}'"

	frappe.db.sql(query)
