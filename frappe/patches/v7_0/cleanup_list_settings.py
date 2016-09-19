from frappe.installer import create_list_settings_table
from frappe.model.utils.list_settings import update_list_settings
import frappe, json

def execute():
	list_settings = frappe.db.sql("select user, doctype, data from __ListSettings", as_dict=1)
	for ls in list_settings:
		if ls and ls.data:
			data = json.loads(ls.data)
			if not data.has_key("fields"):
				continue
			fields = data["fields"]
			for field in fields:
				if "name as" in field:
					fields.remove(field)
			data["fields"] = fields
			
			frappe.db.sql("update __ListSettings set data = %s where user=%s and doctype=%s", 
				(json.dumps(data), ls.user, ls.doctype))
		
