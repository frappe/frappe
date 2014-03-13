# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

import frappe
import frappe.handler
import frappe.client
import frappe.widgets.reportview
from frappe.utils.response import build_response

def handle():
	"""
	/api/method/{methodname} will call a whitelisted method
	/api/resource/{doctype} will query a table
		examples:
			?fields=["name", "owner"]
			?filters=[["Task", "name", "like", "%005"]]
			?limit_start=0
			?limit_page_length=20
	/api/resource/{doctype}/{name} will point to a resource
		GET will return doclist
		POST will insert
		PUT will update
		DELETE will delete
	/api/resource/{doctype}/{name}?run_method={method} will run a whitelisted controller method
	"""
	parts = frappe.request.path[1:].split("/")
	call = doctype = name = None
		
	if len(parts) > 1:
		call = parts[1]
		
	if len(parts) > 2:
		doctype = parts[2]

	if len(parts) > 3:
		name = parts[3]
	
	if call=="method":
		frappe.local.form_dict.cmd = doctype
		return frappe.handler.handle()
	
	elif call=="resource":
		if "run_method" in frappe.local.form_dict:
			bean = frappe.bean(doctype, name)

			if frappe.local.request.method=="GET":
				if not bean.has_permission("read"):
					frappe.throw("No Permission", frappe.PermissionError)
				bean.run_method(frappe.local.form_dict.run_method, **frappe.local.form_dict)
				
			if frappe.local.request.method=="POST":
				if not bean.has_permission("write"):
					frappe.throw("No Permission", frappe.PermissionError)
				bean.run_method(frappe.local.form_dict.run_method, **frappe.local.form_dict)
				frappe.db.commit()

		else:
			if name:
				if frappe.local.request.method=="GET":
					frappe.local.response.update({
						"doclist": frappe.client.get(doctype, 
							name)})
						
				if frappe.local.request.method=="POST":
					frappe.local.response.update({
						"doclist": frappe.client.insert(frappe.local.form_dict.doclist)})
					frappe.db.commit()
				
				if frappe.local.request.method=="PUT":
					frappe.local.response.update({
						"doclist":frappe.client.save(frappe.local.form_dict.doclist)})
					frappe.db.commit()
				
				if frappe.local.request.method=="DELETE":
					frappe.client.delete(doctype, name)
					frappe.local.response.message = "ok"
					
			elif doctype:
				if frappe.local.request.method=="GET":
					frappe.local.response.update({
						"data":  frappe.call(frappe.widgets.reportview.execute, 
							doctype, **frappe.local.form_dict)})
			
			else:
				raise frappe.DoesNotExistError
	
	else:
		raise frappe.DoesNotExistError
	
	return build_response("json")
