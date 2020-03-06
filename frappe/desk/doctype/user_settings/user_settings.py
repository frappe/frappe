# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document

class UserSettings(Document):

	def add_view(self, view):
		self.append("views", view)

	def update_view(self, view_data):
		view = self.get_view(view_data.get("view"))

		if view:
			view.update(view_data)
		else:
			self.add_view(view_data)

	def get_view(self, view_name):
		for view in self.views:
			if view.view == view_name:
				return view

	def get_user_settings(self):
		settings = {
			"last_view": self.last_view,
			"updated_on": self.updated_on
		}

		for view in self.views:
			settings[view.view] = {
				"sort_by": view.sort_by,
				"sort_order": view.sort_order,
				"filters": json.loads(view.filters) if view.filters else [],
				"fields": json.loads(view.fields) if view.fields else []
			}

			if view == "Calendar":
				settings[view.view].update({
					"last_calendar": view.last_calendar
				})
			elif view == "Report":
				settings[view.view].update({
					"add_totals_row": view.add_totals_row
				})

		return json.dumps(settings)

def get_settings(doctype, user):
	if not frappe.db.exists("User Settings", {"document_type": doctype, "user": user}):
		return json.dumps({})

	return frappe.get_doc("User Settings", "{0}-{1}".format(doctype, user)).get_user_settings()

def on_doctype_update():
	frappe.db.add_index("User Settings", ["user", "document_type"])