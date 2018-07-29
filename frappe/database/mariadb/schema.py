from __future__ import unicode_literals

import re
import os
import frappe
from frappe import _
from frappe.utils import cstr, cint, flt
from frappe.database.schema import DBTable, DbColumn

class MariaDBTable(DBTable):
	def create(self):
		add_text = ''

		# columns
		column_defs = self.get_column_definitions()
		if column_defs: add_text += ',\n'.join(column_defs) + ',\n'

		# index
		index_defs = self.get_index_definitions()
		if index_defs: add_text += ',\n'.join(index_defs) + ',\n'

		# create table
		frappe.db.sql("""create table `%s` (
			name varchar({varchar_len}) not null primary key,
			creation datetime(6),
			modified datetime(6),
			modified_by varchar({varchar_len}),
			owner varchar({varchar_len}),
			docstatus int(1) not null default '0',
			parent varchar({varchar_len}),
			parentfield varchar({varchar_len}),
			parenttype varchar({varchar_len}),
			idx int(8) not null default '0',
			%sindex parent(parent),
			index modified(modified))
			ENGINE={engine}
			ROW_FORMAT=COMPRESSED
			CHARACTER SET=utf8mb4
			COLLATE=utf8mb4_unicode_ci""".format(varchar_len=frappe.db.VARCHAR_LEN,
				engine=self.meta.get("engine") or 'InnoDB') % (self.table_name, add_text))


	def get_columns_from_docfields(self):
		"""
			get columns from docfields and custom fields
		"""
		fl = frappe.db.sql("SELECT * FROM tabDocField WHERE parent = %s", self.doctype, as_dict = 1)
		lengths = {}
		precisions = {}
		uniques = {}

		# optional fields like _comments
		if not self.meta.istable:
			for fieldname in frappe.db.OPTIONAL_COLUMNS:
				fl.append({
					"fieldname": fieldname,
					"fieldtype": "Text"
				})

			# add _seen column if track_seen
			if getattr(self.meta, 'track_seen', False):
				fl.append({
					'fieldname': '_seen',
					'fieldtype': 'Text'
				})

		if not frappe.flags.in_install_db and (frappe.flags.in_install != "frappe" or frappe.flags.ignore_in_install):
			custom_fl = frappe.db.sql("""\
				SELECT * FROM `tabCustom Field`
				WHERE dt = %s AND docstatus < 2""", (self.doctype,), as_dict=1)
			if custom_fl: fl += custom_fl

			# apply length, precision and unique from property setters
			for ps in frappe.get_all("Property Setter", fields=["field_name", "property", "value"],
				filters={
					"doc_type": self.doctype,
					"doctype_or_field": "DocField",
					"property": ["in", ["precision", "length", "unique"]]
				}):

				if ps.property=="length":
					lengths[ps.field_name] = cint(ps.value)

				elif ps.property=="precision":
					precisions[ps.field_name] = cint(ps.value)

				elif ps.property=="unique":
					uniques[ps.field_name] = cint(ps.value)

		for f in fl:
			self.columns[f['fieldname']] = DbColumn(self, f['fieldname'],
				f['fieldtype'], lengths.get(f["fieldname"]) or f.get('length'), f.get('default'), f.get('search_index'),
				f.get('options'), uniques.get(f["fieldname"], f.get('unique')), precisions.get(f['fieldname']) or f.get('precision'))

	def is_new(self):
		return self.table_name not in frappe.db.get_tables()

	def alter(self):
		for col in self.columns.values():
			col.build_for_alter_table(self.current_columns.get(col.fieldname.lower(), None))

		query = []

		for col in self.add_column:
			query.append("add column `{}` {}".format(col.fieldname, col.get_definition()))

		for col in self.change_type:
			current_def = self.current_columns.get(col.fieldname.lower(), None)
			query.append("change `{}` `{}` {}".format(current_def["name"], col.fieldname, col.get_definition()))

		for col in self.add_index:
			# if index key not exists
			if not frappe.db.sql("show index from `%s` where key_name = %s" %
					(self.table_name, '%s'), col.fieldname):
				query.append("add index `{}`(`{}`)".format(col.fieldname, col.fieldname))

		for col in self.drop_index:
			if col.fieldname != 'name': # primary key
				# if index key exists
				if frappe.db.sql("""show index from `{0}`
					where key_name=%s
					and Non_unique=%s""".format(self.table_name), (col.fieldname, col.unique)):
					query.append("drop index `{}`".format(col.fieldname))

		for col in self.set_default:
			if col.fieldname=="name":
				continue

			if col.fieldtype in ("Check", "Int"):
				col_default = cint(col.default)

			elif col.fieldtype in ("Currency", "Float", "Percent"):
				col_default = flt(col.default)

			elif not col.default:
				col_default = "null"

			else:
				col_default = '"{}"'.format(col.default.replace('"', '\\"'))

			query.append('alter column `{}` set default {}'.format(col.fieldname, col_default))

		if query:
			try:
				frappe.db.sql("alter table `{}` {}".format(self.table_name, ", ".join(query)))
			except Exception as e:
				# sanitize
				if e.args[0]==1060:
					frappe.throw(str(e))
				elif e.args[0]==1062:
					fieldname = str(e).split("'")[-2]
					frappe.throw(_("{0} field cannot be set as unique in {1}, as there are non-unique existing values".format(
						fieldname, self.table_name)))
				else:
					raise e
