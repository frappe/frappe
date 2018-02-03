# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
import datetime

class GoogleMaps(Document):
	def validate(self):
		if self.enabled:
			if not self.client_key:
				frappe.throw(_("Client key is required"))
			if not self.home_address:
				frappe.throw(_("Home Address is required"))

def round_timedelta(td, period):
	"""Round timedelta"""
	period_seconds = period.total_seconds()
	half_period_seconds = period_seconds / 2
	remainder = td.total_seconds() % period_seconds
	if remainder >= half_period_seconds:
		return datetime.timedelta(seconds=td.total_seconds() + (period_seconds - remainder))
	else:
		return datetime.timedelta(seconds=td.total_seconds() - remainder)

def format_address(address):
	"""Customer Address format """
	address = frappe.get_doc('Address', address)
	return '{}, {}, {}, {}'.format(address.address_line1, address.city, address.pincode, address.country)
