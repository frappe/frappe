# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.modules.export_file import export_to_files
from frappe.model.document import Document
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe import _

class DataMigrationPlan(Document):
	def on_update(self):
		if frappe.flags.in_import:
			return

		if frappe.local.conf.get('developer_mode'):
			record_list =[['Data Migration Plan', self.name]]

			for m in self.mappings:
				record_list.append(['Data Migration Mapping', m.mapping])

			export_to_files(record_list=record_list, record_module=self.module)

	def migrate(self):
		connection = frappe.get_doc('Data Migration Connector', self.connector).get_connection()

		for d in self.mappings:
			# iterating through each mappings
			mapping = frappe.get_doc('Data Migration Mapping', d.mapping)
			mapping.run(connection)

			# TODO - add progress

	def store_mapped_data(self, target):
		""" mapping source field to target field """
		# Iterating through each field to map
		for field in self.mapping.mapping_details:
			source_field = field.remote_fieldname

			# If source field contains a dot linkage, then its a foreign key relation
			if '.' in  source_field:
				arr = source_field.split('.')
				join_data = self.connector.get_join_objects(self.mapping.remote_objectname, field, self.source.get('id'))

				if len(join_data) > 1:
					join_data = join_data[0:1] # ManyToOne mapping, taking the first value only

				target.set(field.local_fieldname, join_data[0][arr[1]])
			else:
				# Else its a simple column to column mapping
				target.set(field.local_fieldname, frappe.as_unicode(self.source.get(source_field)))

		# post process
		if self.mapping.post_process:
			exec self.mapping.post_process in locals()

		try:
			target.save()
		except frappe.DuplicateEntryError:
			target.save()

	def fetch_doctype(self):
		""" Returns correct doctype type - new or existing """
		flag = frappe.db.get_value(self.mapping.local_doctype, {'migration_key': self.source.get('id')})

		if flag:
			# If it is, then fetch that docktype
			return frappe.get_doc(self.mapping.local_doctype, flag)
		else:
			# If not, then check if a data by that name already exist or not
			primary_name = self.mapping.mapping_details[0].local_fieldname
			primary_value = self.source.get(self.mapping.mapping_details[0].remote_fieldname)

			flag_2 = frappe.db.get_value(self.mapping.local_doctype, {primary_name: primary_value})

			if flag_2:
				# If same name is found, fetch that doctype
				return frappe.get_doc(self.mapping.local_doctype, flag_2)
			else :
				#  Else create a new doctype for current data object
				return frappe.new_doc(self.mapping.local_doctype)

@frappe.whitelist()
def migrate(plan):
	plan = frappe.get_doc('Data Migration Plan', plan)
	plan.migrate()

	frappe.clear_messages()

def make_custom_fields(self, dt):
	""" Adding custom field for primary key """
	field = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": 'migration_key'})
	if not field:
		create_custom_field(dt, {
			'label': 'Migration Key',
			'fieldname': 'migration_key',
			'fieldtype': 'Data',
			'hidden': 1,
			'read_only': 1,
			'unique': 1,
		})

def clean_data(self, doctype, condition):
	frappe.db.sql("""delete from `tab{0}`{1}""".format(doctype, condition)) # Incase default frappe data needs to be deleted