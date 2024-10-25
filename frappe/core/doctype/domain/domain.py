# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.model.document import Document
from frappe.utils import cint


class Domain(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		domain: DF.Data
	# end: auto-generated types

	"""Domain documents are created automatically when DocTypes
	with "Restricted" domains are imported during
	installation or migration"""

	def setup_domain(self) -> None:
		"""Setup domain icons, permissions, custom fields etc."""
		self.setup_data()
		self.setup_roles()
		self.setup_properties()
		self.set_values()

		if not cint(frappe.defaults.get_defaults().setup_complete):
			# if setup not complete, setup desktop etc.
			self.setup_sidebar_items()
			self.set_default_portal_role()

		if self.data.custom_fields:
			create_custom_fields(self.data.custom_fields)

		if self.data.on_setup:
			# custom on_setup method
			frappe.get_attr(self.data.on_setup)()

	def remove_domain(self) -> None:
		"""Unset domain settings"""
		self.setup_data()

		if self.data.restricted_roles:
			for role_name in self.data.restricted_roles:
				if frappe.db.exists("Role", role_name):
					role = frappe.get_doc("Role", role_name)
					role.disabled = 1
					role.save()

		self.remove_custom_field()

	def remove_custom_field(self) -> None:
		"""Remove custom_fields when disabling domain"""
		if self.data.custom_fields:
			for doctype in self.data.custom_fields:
				custom_fields = self.data.custom_fields[doctype]

				# custom_fields can be a list or dict
				if isinstance(custom_fields, dict):
					custom_fields = [custom_fields]

				for custom_field_detail in custom_fields:
					custom_field_name = frappe.db.get_value(
						"Custom Field", dict(dt=doctype, fieldname=custom_field_detail.get("fieldname"))
					)
					if custom_field_name:
						frappe.delete_doc("Custom Field", custom_field_name)

	def setup_roles(self) -> None:
		"""Enable roles that are restricted to this domain"""
		if self.data.restricted_roles:
			user = frappe.get_doc("User", frappe.session.user)
			for role_name in self.data.restricted_roles:
				user.append("roles", {"role": role_name})
				if not frappe.db.get_value("Role", role_name):
					frappe.get_doc(doctype="Role", role_name=role_name).insert()
					continue

				role = frappe.get_doc("Role", role_name)
				role.disabled = 0
				role.save()
			user.save()

	def setup_data(self, domain=None) -> None:
		"""Load domain info via hooks"""
		self.data = frappe.get_domain_data(self.name)

	def get_domain_data(self, module):
		return frappe.get_attr(frappe.get_hooks("domains")[self.name] + ".data")

	def set_default_portal_role(self) -> None:
		"""Set default portal role based on domain"""
		if self.data.get("default_portal_role"):
			frappe.db.set_single_value(
				"Portal Settings", "default_role", self.data.get("default_portal_role")
			)

	def setup_properties(self) -> None:
		if self.data.properties:
			for args in self.data.properties:
				frappe.make_property_setter(args)

	def set_values(self) -> None:
		"""set values based on `data.set_value`"""
		if self.data.set_value:
			for args in self.data.set_value:
				frappe.reload_doctype(args[0])
				doc = frappe.get_doc(args[0], args[1] or args[0])
				doc.set(args[2], args[3])
				doc.save()

	def setup_sidebar_items(self) -> None:
		"""Enable / disable sidebar items"""
		if self.data.allow_sidebar_items:
			# disable all
			frappe.db.sql("update `tabPortal Menu Item` set enabled=0")

			# enable
			frappe.db.sql(
				"""update `tabPortal Menu Item` set enabled=1
				where route in ({})""".format(", ".join(f'"{d}"' for d in self.data.allow_sidebar_items))
			)

		if self.data.remove_sidebar_items:
			# disable all
			frappe.db.sql("update `tabPortal Menu Item` set enabled=1")

			# enable
			frappe.db.sql(
				"""update `tabPortal Menu Item` set enabled=0
				where route in ({})""".format(", ".join(f'"{d}"' for d in self.data.remove_sidebar_items))
			)
