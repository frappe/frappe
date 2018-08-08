# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils.nestedset import NestedSet


class AdministrativeArea(NestedSet):
	def autoname(self):
		"""
		append parent name to administrative area if title is duplicate
		"""
		self.name = str(self.title).title()
		if frappe.db.exists("Administrative Area", self.name):
			if frappe.db.get_value("Administrative Area", self.name, "parent_administrative_area") == self.parent_administrative_area:
				frappe.throw("{0} already exists".format(self.name))
			else:
				#self.name = "{self.name}-{self.parent_administrative_area}".format(self=self)
				self.name = "{0}-{1}".format(self.name, self.parent_administrative_area)
				self.name = str(self.name).title()

	def on_update(self):
		super(AdministrativeArea, self).on_update()
		self.validate_one_root()


def on_doctype_update():
	frappe.db.add_index("Administrative Area", ["lft", "rgt"])
	#frappe.db.add_index("Administrative Area", ["administrative_area_type", "title"])
