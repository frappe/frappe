# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class GoogleMaps(Document):
	def validate(self):
		if self.enable:
			if not frappe.db.get_single_value("Google Settings", "enable"):
				frappe.throw(_("Enable Google Settings for Google Maps Integration."))

			if not frappe.db.get_single_value("Google Settings", "api_key"):
				frappe.throw(_("Enter API Key for Google Maps Integration in Google Settings."))

	def get_client(self):
		if not self.enable:
			frappe.throw(_("Google Maps Integration is not enabled."))

		import googlemaps

		try:
			client = googlemaps.Client(key=frappe.db.get_single_value("Google Settings", "api_key"))
		except Exception as e:
			frappe.throw(e.message)

		return client

