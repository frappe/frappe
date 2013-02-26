# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

from __future__ import unicode_literals
import webnotes
import webnotes.model.doc
import webnotes.model.code

conn = webnotes.conn

@webnotes.whitelist()
def get(name):
	"""
	   Return the :term:`doclist` of the `Page` specified by `name`
	"""
	from webnotes.model.code import get_obj
	page = get_obj('Page', name, with_children=1)
	page.get_from_files()
	return page.doclist

@webnotes.whitelist(allow_guest=True)
def getpage():
	"""
	   Load the page from `webnotes.form` and send it via `webnotes.response`
	"""
	page = webnotes.form_dict.get('name')
	doclist = get(page)
	
	if has_permission(doclist):
		# load translations
		if webnotes.lang != "en":
			from webnotes.modules import get_doc_path
			from webnotes.translate import get_lang_data
			d = doclist[0]
			messages = get_lang_data(get_doc_path(d.module, d.doctype, d.name), 
				webnotes.lang, 'js')
			webnotes.response["__messages"] = messages
				
		webnotes.response['docs'] = doclist
	else:
		webnotes.response['403'] = 1
		raise webnotes.PermissionError, 'No read permission for Page %s' % \
			(doclist[0].title or page, )
		
def has_permission(page_doclist):
	if webnotes.user.name == "Administrator" or "System Manager" in webnotes.user.get_roles():
		return True
		
	page_roles = [d.role for d in page_doclist if d.fields.get("doctype")=="Page Role"]
	if webnotes.user.name == "Guest" and not (page_roles and "Guest" in page_roles):
		return False
	
	elif page_roles and not (set(page_roles) & set(webnotes.user.get_roles())):
		return False

	return True