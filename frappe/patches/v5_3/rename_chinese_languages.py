# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.translate import rename_language

def execute():
	language_map = {
		"中国（简体）": "简体中文",
		"中國（繁體）": "繁体中文"
	}

	for old_name, new_name in language_map.items():
		rename_language(old_name, new_name)
