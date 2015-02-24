from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("core", "doctype", "docperm")
	
	# delete same as cancel (map old permissions)
	frappe.db.sql("""update tabDocPerm set `delete`=ifnull(`cancel`,0)""")
	
	# can't cancel if can't submit
	frappe.db.sql("""update tabDocPerm set `cancel`=0 where ifnull(`submit`,0)=0""")
	
	frappe.clear_cache()