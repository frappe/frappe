# Copyright (c) 2017, Frappe and Contributors
# License: GNU General Public License v3. See license.txt
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import frappe
from frappe.desk.doctype.desktop_icon.desktop_icon import clear_desktop_icons_cache

def execute():
	desktop_icons = frappe.db.sql("""
		select name, label
		from
			`tabDesktop Icon` 
		where 
			_doctype is not null 
			and _doctype != '' 
			and _doctype != label""", as_dict=1)
			
	for d in desktop_icons:
		if not is_english(d.label):
			frappe.db.sql("""update `tabDesktop Icon` 
				set module_name=_doctype, label=_doctype where name=%s""", d.name)
			
	clear_desktop_icons_cache()
			

def is_english(s):
    try:
        s.decode('ascii')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return False
    else:
        return True