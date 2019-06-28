# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class GoogleMaps(Document):
	def validate(self):
		if self.enable and not frappe.db.get_single_value("Google Settings", "enable"):
			frappe.throw(_("Enable Google API in Google Settings."))

	def get_client(self):
		if not self.enable:
			frappe.throw(_("Google Maps integration is not enabled"))

		import googlemaps

		try:
			client_id = frappe.db.get_single_value("Google Settings", "client_id")
			client = googlemaps.Client(key=client_id)
		except Exception as e:
			frappe.throw(e.message)

		return client

