# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
def on_doctype_update():
	if not frappe.conn.sql("""show index from `tabDefaultValue` 
		where Key_name="defaultvalue_parent_defkey_index" """):
		frappe.conn.commit()
		frappe.conn.sql("""alter table `tabDefaultValue` 
			add index defaultvalue_parent_defkey_index(parent, defkey)""")

	if not frappe.conn.sql("""show index from `tabDefaultValue` 
		where Key_name="defaultvalue_parent_parenttype_index" """):
		frappe.conn.commit()
		frappe.conn.sql("""alter table `tabDefaultValue` 
			add index defaultvalue_parent_parenttype_index(parent, parenttype)""")