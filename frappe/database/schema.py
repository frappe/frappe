from __future__ import unicode_literals

import re
import frappe

from frappe import _
from frappe.utils import cstr, cint, flt


class InvalidColumnName(frappe.ValidationError): pass

class DBTable:
	def __init__(self, doctype, meta=None):
		self.doctype = doctype
		self.table_name = 'tab{}'.format(doctype)
		self.meta = meta or frappe.get_meta(doctype, False)
		self.columns = {}
		self.current_columns = {}

		# lists for change
		self.add_column = []
		self.change_type = []
		self.change_name = []
		self.add_unique = []
		self.add_index = []
		self.drop_index = []
		self.set_default = []

		# load
		self.get_columns_from_docfields()

	def sync(self):
		if self.is_new():
			self.create()
		else:
			frappe.cache().hdel('table_columns', self.table_name)
			self.alter()

	def create(self):
		pass

	def get_column_definitions(self):
		column_list = [] + frappe.db.DEFAULT_COLUMNS
		ret = []
		for k in list(self.columns):
			if k not in column_list:
				d = self.columns[k].get_definition()
				if d:
					ret.append('`'+ k + '` ' + d)
					column_list.append(k)
		return ret

	def get_index_definitions(self):
		ret = []
		for key, col in self.columns.items():
			if (col.set_index
				and not col.unique
				and col.fieldtype in frappe.db.type_map
				and frappe.db.type_map.get(col.fieldtype)[0]
				not in ('text', 'longtext')):
				ret.append('index `' + key + '`(`' + key + '`)')
		return ret

	def get_columns_from_docfields(self):
		"""
			get columns from docfields and custom fields
		"""
		fields = self.meta.get_fieldnames_with_value(True)

		# optional fields like _comments
		if not self.meta.get('istable'):
			for fieldname in frappe.db.OPTIONAL_COLUMNS:
				fields.append({
					"fieldname": fieldname,
					"fieldtype": "Text"
				})

			# add _seen column if track_seen
			if self.meta.get('track_seen'):
				fields.append({
					'fieldname': '_seen',
					'fieldtype': 'Text'
				})

		for field in fields:
			self.columns[field.get('fieldname')] = DbColumn(
				self,
				field.get('fieldname'),
				field.get('fieldtype'),
				field.get('length'),
				field.get('default'),
				field.get('search_index'),
				field.get('options'),
				field.get('unique'),
				field.get('precision')
			)

	def validate(self):
		"""Check if change in varchar length isn't truncating the columns"""
		if self.is_new():
			return

		self.setup_table_columns()

		columns = [frappe._dict({"fieldname": f, "fieldtype": "Data"}) for f in
			frappe.db.STANDARD_VARCHAR_COLUMNS]
		columns += self.columns.values()

		for col in columns:
			if len(col.fieldname) >= 64:
				frappe.throw(_("Fieldname is limited to 64 characters ({0})")
					.format(frappe.bold(col.fieldname)))

			if 'varchar' in frappe.db.type_map.get(col.fieldtype, ()):

				# validate length range
				new_length = cint(col.length) or cint(frappe.db.VARCHAR_LEN)
				if not (1 <= new_length <= 1000):
					frappe.throw(_("Length of {0} should be between 1 and 1000").format(col.fieldname))

				current_col = self.current_columns.get(col.fieldname, {})
				if not current_col:
					continue
				current_type = self.current_columns[col.fieldname]["type"]
				current_length = re.findall(r'varchar\(([\d]+)\)', current_type)
				if not current_length:
					# case when the field is no longer a varchar
					continue
				current_length = current_length[0]
				if cint(current_length) != cint(new_length):
					try:
						# check for truncation
						max_length = frappe.db.sql("""SELECT MAX(CHAR_LENGTH(`{fieldname}`)) FROM `tab{doctype}`"""
							.format(fieldname=col.fieldname, doctype=self.doctype))

					except frappe.db.InternalError as e:
						if frappe.db.is_missing_column(e):
							# Unknown column 'column_name' in 'field list'
							continue
						else:
							raise

					if max_length and max_length[0][0] and max_length[0][0] > new_length:
						if col.fieldname in self.columns:
							self.columns[col.fieldname].length = current_length

						frappe.msgprint(_("""Reverting length to {0} for '{1}' in '{2}';
							Setting the length as {3} will cause truncation of data.""")
							.format(current_length, col.fieldname, self.doctype, new_length))

	def is_new(self):
		return self.table_name not in frappe.db.get_tables()

	def setup_table_columns(self):
		# TODO: figure out a way to get key data
		for c in frappe.db.get_table_columns_description(self.table_name):
			self.current_columns[c.name.lower()] = c

	def alter(self):
		pass


class DbColumn:
	def __init__(self, table, fieldname, fieldtype, length, default,
		set_index, options, unique, precision):
		self.table = table
		self.fieldname = fieldname
		self.fieldtype = fieldtype
		self.length = length
		self.set_index = set_index
		self.default = default
		self.options = options
		self.unique = unique
		self.precision = precision

	def get_definition(self, with_default=1):
		column_def = get_definition(self.fieldtype, precision=self.precision, length=self.length)

		if not column_def:
			return column_def

		if self.fieldtype in ("Check", "Int"):
			default_value = cint(self.default) or 0
			column_def += ' not null default {0}'.format(default_value)

		elif self.fieldtype in ("Currency", "Float", "Percent"):
			default_value = flt(self.default) or 0
			column_def += ' not null default {0}'.format(default_value)

		elif self.default and (self.default not in frappe.db.DEFAULT_SHORTCUTS) \
			and not self.default.startswith(":") and column_def not in ('text', 'longtext'):
			column_def += " default {}".format(frappe.db.escape(self.default))

		if self.unique and (column_def not in ('text', 'longtext')):
			column_def += ' unique'

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
			return

		# type
		if (current_def['type'] != column_type):
			self.table.change_type.append(self)

		# unique
		if((self.unique and not current_def['unique']) and column_type not in ('text', 'longtext')):
			self.table.add_unique.append(self)

		# default
		if (self.default_changed(current_def)
			and (self.default not in frappe.db.DEFAULT_SHORTCUTS)
			and not cstr(self.default).startswith(":")
			and not (column_type in ['text','longtext'])):
			self.table.set_default.append(self)

		# index should be applied or dropped irrespective of type change
		if ((current_def['index'] and not self.set_index and not self.unique)
			or (current_def['unique'] and not self.unique)):
			# to drop unique you have to drop index
			self.table.drop_index.append(self)

		elif (not current_def['index'] and self.set_index) and not (column_type in ('text', 'longtext')):
			self.table.add_index.append(self)

	def default_changed(self, current_def):
		if "decimal" in current_def['type']:
			return self.default_changed_for_decimal(current_def)
		else:
			cur_default = current_def['default']
			new_default = self.default
			if cur_default == "NULL" or cur_default is None:
				cur_default = None
			else:
				# Strip quotes from default value
				# eg. database returns default value as "'System Manager'"
				cur_default = cur_default.lstrip("'").rstrip("'")

			fieldtype = self.fieldtype
			if fieldtype in ['Int', 'Check']:
				cur_default = cint(cur_default)
				new_default = cint(new_default)
			elif fieldtype in ['Currency', 'Float', 'Percent']:
				cur_default = flt(cur_default)
				new_default = flt(new_default)
			return cur_default != new_default

	def default_changed_for_decimal(self, current_def):
		try:
			if current_def['default'] in ("", None) and self.default in ("", None):
				# both none, empty
				return False

			elif current_def['default'] in ("", None):
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
				return float(current_def['default'])!=float(self.default)
		except TypeError:
			return True

def validate_column_name(n):
	special_characters = re.findall(r"[\W]", n, re.UNICODE)
	if special_characters:
		special_characters = ", ".join('"{0}"'.format(c) for c in special_characters)
		frappe.throw(_("Fieldname {0} cannot have special characters like {1}").format(
			frappe.bold(cstr(n)), special_characters), frappe.db.InvalidColumnName)
	return n

def validate_column_length(fieldname):
	if len(fieldname) > frappe.db.MAX_COLUMN_LENGTH:
		frappe.throw(_("Fieldname is limited to 64 characters ({0})").format(fieldname))

def get_definition(fieldtype, precision=None, length=None):
	d = frappe.db.type_map.get(fieldtype)

	# convert int to long int if the length of the int is greater than 11
	if fieldtype == "Int" and length and length > 11:
		d = frappe.db.type_map.get("Long Int")

	if not d: return

	coltype = d[0]
	size = d[1] if d[1] else None

	if size:
		if fieldtype in ["Float", "Currency", "Percent"] and cint(precision) > 6:
			size = '21,9'

		if coltype == "varchar" and length:
			size = length

	if size is not None:
		coltype = "{coltype}({size})".format(coltype=coltype, size=size)

	return coltype

def add_column(doctype, column_name, fieldtype, precision=None):
	if column_name in frappe.db.get_table_columns(doctype):
		# already exists
		return

	frappe.db.commit()
	frappe.db.sql("alter table `tab%s` add column %s %s" % (doctype,
		column_name, get_definition(fieldtype, precision)))
