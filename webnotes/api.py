# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

import webnotes
import webnotes.handler
import webnotes.client
import webnotes.widgets.reportview
from webnotes.utils.response import build_response, report_error

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
	parts = webnotes.request.path[1:].split("/")
	call = doctype = name = None
	
	if len(parts) > 1:
		call = parts[1]
		
	if len(parts) > 2:
		doctype = parts[2]

	if len(parts) > 3:
		name = parts[3]
	
	try:
		if call=="method":
			webnotes.local.form_dict.cmd = doctype
			webnotes.handler.handle()
			return
		
		elif call=="resource":
			if "run_method" in webnotes.local.form_dict:
				bean = webnotes.bean(doctype, name)

				if webnotes.local.request.method=="GET":
					if not bean.has_permission("read"):
						webnotes.throw("No Permission", webnotes.PermissionError)
					webnotes.local.response.update({"data": bean.run_method(webnotes.local.form_dict.run_method, 
						**webnotes.local.form_dict)})
					
				if webnotes.local.request.method=="POST":
					if not bean.has_permission("write"):
						webnotes.throw("No Permission", webnotes.PermissionError)
					webnotes.local.response.update({"data":bean.run_method(webnotes.local.form_dict.run_method, 
						**webnotes.local.form_dict)})
					webnotes.conn.commit()

			else:
				if name:
					if webnotes.local.request.method=="GET":
						webnotes.local.response.update({
							"doclist": webnotes.client.get(doctype, 
								name)})
							
					if webnotes.local.request.method=="POST":
						webnotes.local.response.update({
							"doclist": webnotes.client.insert(webnotes.local.form_dict.doclist)})
						webnotes.conn.commit()
					
					if webnotes.local.request.method=="PUT":
						webnotes.local.response.update({
							"doclist":webnotes.client.save(webnotes.local.form_dict.doclist)})
						webnotes.conn.commit()
					
					if webnotes.local.request.method=="DELETE":
						webnotes.client.delete(doctype, name)
						webnotes.local.response.message = "ok"
						
				elif doctype:
					if webnotes.local.request.method=="GET":
						webnotes.local.response.update({
							"data":  webnotes.call(webnotes.widgets.reportview.execute, 
								doctype, **webnotes.local.form_dict)})
				
				else:
					raise Exception("Bad API")
		
		else:
			raise Exception("Bad API")
			
	except Exception, e:
		report_error(500)
	
	build_response()
