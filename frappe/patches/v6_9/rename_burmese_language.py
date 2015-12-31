# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.translate import rename_language

def execute():
	rename_language("Melayu", "မြန်မာ")
