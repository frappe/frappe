# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doctype('Custom Role')
	frappe.reload_doctype('Page')
	frappe.db.sql(""" update `tabCustom Role` set 
		`tabCustom Role`.ref_doctype = (select ref_doctype from `tabReport` where name = `tabCustom Role`.report)
		where `tabCustom Role`.report is not null""")
		
	frappe.db.sql("""update 
		`tabPage` set system_page = 1 where name not in('setup-wizard', 'modules_setup')""")
	