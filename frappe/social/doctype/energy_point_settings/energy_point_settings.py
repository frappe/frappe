# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe
from frappe.model.document import Document
import frappe

class EnergyPointSettings(Document):
	pass

def is_energy_point_enabled():
	return frappe.get_cached_value('Energy Point Settings', None, 'enabled')
