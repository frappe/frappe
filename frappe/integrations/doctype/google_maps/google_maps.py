# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import datetime

class GoogleMaps(Document):
	pass

def round_timedelta(td, period):
	"""Round timedelta"""
	period_seconds = period.total_seconds()
	half_period_seconds = period_seconds / 2
	remainder = td.total_seconds() % period_seconds
	if remainder >= half_period_seconds:
		return datetime.timedelta(seconds=td.total_seconds() + (period_seconds - remainder))
	else:
		return datetime.timedelta(seconds=td.total_seconds() - remainder)

def customer_address_format(address):
	"""Customer Address format """
	address = frappe.get_doc('Address', address)
	return '{}, {}, {}, {}'.format(address.address_line1, address.city, address.pincode, address.country)
