# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.modules.export_file import export_to_files
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.model.document import Document

class DataMigrationPlan(Document):
	def after_insert(self):
		self.make_custom_fields_for_mappings()

	def on_update(self):
		if frappe.flags.in_import or frappe.flags.in_test:
			return

		if frappe.local.conf.get('developer_mode'):
			record_list =[['Data Migration Plan', self.name]]

			for m in self.mappings:
				record_list.append(['Data Migration Mapping', m.mapping])

			export_to_files(record_list=record_list, record_module=self.module)

	def make_custom_fields_for_mappings(self):
		label = self.name + ' ID'
		fieldname = frappe.scrub(label)

		df = {
			'label': label,
			'fieldname': fieldname,
			'fieldtype': 'Data',
			'hidden': 1,
			'read_only': 1,
			'unique': 1
		}

		for m in self.mappings:
			mapping = frappe.get_doc('Data Migration Mapping', m.mapping)
			create_custom_field(mapping.local_doctype, df)
			mapping.migration_id_field = fieldname
			mapping.save()

		# Create custom field in Deleted Document
		create_custom_field('Deleted Document', df)

	def pre_process_doc(self, mapping_name, doc):
		module = self.get_mapping_module(mapping_name)

		if module and hasattr(module, 'pre_process'):
			return module.pre_process(doc)
		return doc

	def post_process_doc(self, mapping_name, doc):
		module = self.get_mapping_module(mapping_name)

		if module and hasattr(module, 'post_process'):
			return module.post_process(doc)
		return doc

	def get_mapping_module(self, mapping_name):
		try:
			module = frappe.get_module('erpnext.{module}.data_migration_mapping.{mapping_name}'.format(
				module=frappe.scrub(self.module),
				mapping_name=frappe.scrub(mapping_name)
			))
			return module
		except ImportError:
			return None
