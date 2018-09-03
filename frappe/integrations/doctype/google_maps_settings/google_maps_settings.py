# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import googlemaps

import frappe
from frappe import _
from frappe.model.document import Document


class GoogleMapsSettings(Document):
	def validate(self):
		if self.enabled:
			if not self.client_key:
				frappe.throw(_("Client key is required"))
			if not self.home_address:
				frappe.throw(_("Home Address is required"))

	def get_client(self):
		if not self.enabled:
			frappe.throw(_("Google Maps integration is not enabled"))

		try:
			client = googlemaps.Client(key=self.client_key)
		except Exception as e:
			frappe.throw(e.message)

		return client
