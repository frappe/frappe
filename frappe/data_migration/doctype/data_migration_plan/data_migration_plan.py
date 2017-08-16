# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe import _

class DataMigrationPlan(Document):
	def migrate(self):
		source_connector = frappe.get_doc('Data Migration Connector', self.source_connector)
		source_connector.connect()

		for x in self.apps:
			app = frappe.get_doc('Data Migration App', x.app)

			for d in app.mappings:
				mapping = frappe.get_doc('Data Migration Mapping', d.mapping)
				data = source_connector.get_objects(mapping.source_objectname, mapping.condition, "*")
				make_custom_fields(mapping.target_doctype)

				for i, source in enumerate(data):

					flag = frappe.db.get_value(mapping.target_doctype, {'migration_key': source.get('id')})

					if flag:
						target = frappe.get_doc(mapping.target_doctype, flag)
					else:
						primary_name = mapping.mapping_details[0].target_fieldname
						primary_value = source.get(mapping.mapping_details[0].source_fieldname)
						flag_2 = frappe.db.get_value(mapping.target_doctype, {primary_name: primary_value})

						if flag_2:
							target = frappe.get_doc(mapping.target_doctype, flag_2)
						else :
							target = frappe.new_doc(mapping.target_doctype)

					target.set('migration_key', source.get('id'))

					for field in mapping.mapping_details:
						source_field = field.source_fieldname

						if '.' in  source_field:
							arr = source_field.split('.')
							join_data = source_connector.get_join_objects(mapping.source_objectname, field, source.get('id'))

							target.set(field.target_fieldname, join_data[0][arr[1]])
						else:
							target.set(field.target_fieldname, source.get(source_field))

						if field.formula:
							print field.formula

					# post process
					if mapping.post_process:
						exec mapping.post_process in locals()

					try:
						target.save()
					except frappe.DuplicateEntryError:
						target.save()

					frappe.publish_progress(float(i)*100/len(data),
						title = _('Migrating {0}').format(target.doctype), doctype=self.doctype, docname=self.name)


				frappe.publish_progress(100,
					title = _('Migrating {0}').format(target.doctype), doctype=self.doctype, docname=self.name)

@frappe.whitelist()
def migrate(plan):
# 	frappe.enqueue(_migrate, plan=plan)

# def _migrate(plan):
	plan = frappe.get_doc('Data Migration Plan', plan)
	plan.migrate()

	frappe.clear_messages()

@frappe.whitelist()
def make_custom_fields(dt):
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