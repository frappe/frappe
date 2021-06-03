# -*- coding: utf-8 -*-
import frappe
from frappe.translate import rename_language

def execute():
	rename_language("বাঙালি", "বাংলা")