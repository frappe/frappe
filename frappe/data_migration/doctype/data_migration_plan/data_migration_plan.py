# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import unicode_literals

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.model.document import Document
from frappe.modules import get_module_path, scrub_dt_dn
from frappe.modules.export_file import create_init_py, export_to_files


def get_mapping_module(module, mapping_name):
	app_name = frappe.db.get_value("Module Def", module, "app_name")
	mapping_name = frappe.scrub(mapping_name)
	module = frappe.scrub(module)

	try:
		return frappe.get_module(
			"{app_name}.{module}.data_migration_mapping.{mapping_name}".format(
				app_name=app_name,
				mapping_name=mapping_name,
				module=module,
			)
		)
	except ImportError:
		return None


class DataMigrationPlan(Document):
	def on_update(self):
		# update custom fields in mappings
		self.make_custom_fields_for_mappings()

		if frappe.flags.in_import or frappe.flags.in_test:
			return

		if frappe.local.conf.get("developer_mode"):
			record_list = [["Data Migration Plan", self.name]]

			for m in self.mappings:
				record_list.append(["Data Migration Mapping", m.mapping])

			export_to_files(record_list=record_list, record_module=self.module)

			for m in self.mappings:
				dt, dn = scrub_dt_dn("Data Migration Mapping", m.mapping)
				create_init_py(get_module_path(self.module), dt, dn)

	def make_custom_fields_for_mappings(self):
		frappe.flags.ignore_in_install = True
		label = self.name + " ID"
		fieldname = frappe.scrub(label)

		df = {
			"label": label,
			"fieldname": fieldname,
			"fieldtype": "Data",
			"hidden": 1,
			"read_only": 1,
			"unique": 1,
			"no_copy": 1,
		}

		for m in self.mappings:
			mapping = frappe.get_doc("Data Migration Mapping", m.mapping)
			create_custom_field(mapping.local_doctype, df)
			mapping.migration_id_field = fieldname
			mapping.save()

		# Create custom field in Deleted Document
		create_custom_field("Deleted Document", df)
		frappe.flags.ignore_in_install = False

	def pre_process_doc(self, mapping_name, doc):
		module = get_mapping_module(self.module, mapping_name)

		if module and hasattr(module, "pre_process"):
			return module.pre_process(doc)
		return doc

	def post_process_doc(self, mapping_name, local_doc=None, remote_doc=None):
		module = get_mapping_module(self.module, mapping_name)

		if module and hasattr(module, "post_process"):
			return module.post_process(local_doc=local_doc, remote_doc=remote_doc)
