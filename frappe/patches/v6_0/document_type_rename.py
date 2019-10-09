from __future__ import unicode_literals
import frappe

def execute():
	frappe.db.sql("""update tabDocType set document_type='Document'
		where document_type='Transaction'""")
	frappe.db.sql("""update tabDocType set document_type='Setup'
		where document_type='Master'""")		
