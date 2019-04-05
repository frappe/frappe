from __future__ import unicode_literals
import frappe, json

def execute():
	if frappe.db.table_exists("__ListSettings"):	
		list_settings = frappe.db.sql("select user, doctype, data from __ListSettings", as_dict=1)
		for ls in list_settings:
			if ls and ls.data:
				data = json.loads(ls.data)
				if "fields" not in data:
					continue
				fields = data["fields"]
				for field in fields:
					if "name as" in field:
						fields.remove(field)
				data["fields"] = fields
			
				frappe.db.sql("update __ListSettings set data = %s where user=%s and doctype=%s", 
					(json.dumps(data), ls.user, ls.doctype))					
		
