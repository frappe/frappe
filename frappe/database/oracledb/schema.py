from operator import index

from oauthlib.uri_validate import query

import frappe
from frappe import _
from frappe.database.schema import DBTable


class OracleDBTable(DBTable):

	def __init__(self, doctype, meta=None):
		super().__init__(doctype, meta)

	def get_column_definitions(self):
		column_list = [*frappe.db.DEFAULT_COLUMNS]
		ret = []
		for k in list(self.columns):
			if k not in column_list:
				d = self.columns[k].get_definition(syntax_template=" DEFAULT {} NOT NULL")
				if d:
					ret.append('"' + k + '" ' + d)
					column_list.append(k)
		return ret

	def get_index_definitions(self):
		return [
			'index "' + key + '"("' + key + '")'
			for key, col in self.columns.items()
			if (
				col.set_index
				and not col.unique
				and col.fieldtype in frappe.db.type_map
				and frappe.db.type_map.get(col.fieldtype)[0] not in ("text", "longtext")
			)
		]

	def create(self):
		additional_definitions = []
		varchar_len = frappe.db.VARCHAR_LEN
		name_column = f'"name" VARCHAR2({varchar_len}) PRIMARY KEY'

		# columns
		column_defs = self.get_column_definitions()
		if column_defs:
			additional_definitions += column_defs

		# child table columns
		if self.meta.get("istable", default=0):
			additional_definitions += [
				f'"parent" VARCHAR2({varchar_len})',
				f'"parentfield" VARCHAR2({varchar_len})',
				f'"parenttype" VARCHAR2({varchar_len})'
			]

		# creating sequence(s)
		if not self.meta.issingle and self.meta.autoname == "autoincrement":
			sequence_name = f"{self.table_name}_seq"
			frappe.db.sql(f'CREATE SEQUENCE "{sequence_name}" START WITH 1 INCREMENT BY 1')
			name_column = '"name" NUMBER PRIMARY KEY'

		additional_definitions = ", ".join(additional_definitions)

		# create table
		query = f'CREATE TABLE {frappe.conf.db_name.upper()}."{self.table_name}" ({name_column}, ' \
				f'"creation" TIMESTAMP, "modified" TIMESTAMP, "modified_by" ' \
				f'VARCHAR2({varchar_len}), "owner" VARCHAR2({varchar_len}), "docstatus" NUMBER(1) ' \
				f'DEFAULT 0 NOT NULL, "idx" NUMBER DEFAULT 0 NOT NULL, {additional_definitions})'
		index_defs = self.get_index_definitions()
		frappe.db.sql(query)
		frappe.db.commit()

		if not self.meta.get("istable", default=0):
			frappe.db.sql(
				f'CREATE INDEX {frappe.conf.db_name.upper()}."{self.table_name}_creation_index" ON "{self.table_name}" ("creation") ')
			if self.meta.sort_field == "modified":
				frappe.db.sql(
					f'CREATE INDEX {frappe.conf.db_name.upper()}."{self.table_name}_modified_index" ON "{self.table_name}" ("modified") ')

			frappe.db.commit()

		# for i in index_defs:
		# 	# todo: Important
		# 	frappe.db.sql(f'CREATE INDEX {i}')

	def alter(self):
		if self.table_name == 'tabDocType':
			print("alter tabDocType")
			print('1')
		for col in self.columns.values():
			col.build_for_alter_table(self.current_columns.get(col.fieldname))

		add_column_query = [
			f' "{col.fieldname}" {col.get_definition(syntax_template=" default {} not null")}'
			for col in self.add_column]

		# if alter_pk := self.alter_primary_key():
		# 	modify_column_query.append(alter_pk)

		try:
			for ii in add_column_query:
				_query = f'ALTER TABLE "{self.table_name}" ADD {ii}'
				frappe.db.sql(_query)
				frappe.db.commit()

			for col in set(self.change_type + self.set_default):
				# Add temp columns
				add_statement = 'ADD "temp_{}" {}'.format(
					col.fieldname,
					col.get_definition(for_modification=True,
									   syntax_template=" default {} not null")
				)
				query_add = f'ALTER TABLE "{self.table_name}" {add_statement}'
				frappe.db.sql(query_add)
				frappe.db.commit()

				# Set query
				query_set = f'UPDATE "{self.table_name}" SET "temp_{col.fieldname}" = "{col.fieldname}"'
				frappe.db.sql(query_set)
				frappe.db.commit()

				# Drop
				drop_statement = f' DROP COLUMN "{col.fieldname}" '
				query_drop = f'ALTER TABLE "{self.table_name}" {drop_statement}'
				frappe.db.sql(query_drop)
				frappe.db.commit()

				# Rename
				rename_statement = f' RENAME COLUMN "temp_{col.fieldname}" TO "{col.fieldname}" '
				query_rename = f'ALTER TABLE "{self.table_name}" {rename_statement}'
				frappe.db.sql(query_rename)
				frappe.db.commit()

		except Exception as e:
			if query := locals().get("query"):
				print(f"\n\nFailed to alter schema using query: {query}")
			raise

	def alter_primary_key(self) -> str | None:
		autoname = self.meta.autoname
		if autoname == "UUID" and frappe.db.get_column_type(self.doctype, "name") != "RAW":
			if not frappe.db.get_value(self.doctype, {}, order_by=None):
				return 'MODIFY "name" RAW(16)'
			else:
				frappe.throw(
					_("Primary key of doctype {0} cannot be changed as there are existing values.").format(
						self.doctype
					)
				)

		if autoname != "UUID" and frappe.db.get_column_type(self.doctype, "name") == "RAW":
			return f'MODIFY "name" VARCHAR2({frappe.db.VARCHAR_LEN})'
