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
import json

@webnotes.whitelist()
def get(doctype, name=None, filters=None):
	if filters and not name:
		name = webnotes.conn.get_value(doctype, json.loads(filters))
		if not name:
			raise Exception, "No document found for given filters"
	return [d.fields for d in webnotes.bean(doctype, name).doclist]

@webnotes.whitelist()
def get_value(doctype, fieldname, filters=None, as_dict=True):
	if not webnotes.has_permission(doctype):
		webnotes.msgprint("No Permission", raise_exception=True)
		
	if fieldname and fieldname.startswith("["):
		fieldname = json.loads(fieldname)
	return webnotes.conn.get_value(doctype, json.loads(filters), fieldname, as_dict=as_dict)

@webnotes.whitelist()
def insert(doclist):
	if isinstance(doclist, basestring):
		doclist = json.loads(doclist)
	
	doclist[0]["__islocal"] = 1
	return save(doclist)

@webnotes.whitelist()
def save(doclist):
	if isinstance(doclist, basestring):
		doclist = json.loads(doclist)

	doclistobj = webnotes.bean(doclist)
	doclistobj.save()
	
	return [d.fields for d in doclist]

@webnotes.whitelist()
def submit(doclist):
	if isinstance(doclist, basestring):
		doclist = json.loads(doclist)

	doclistobj = webnotes.bean(doclist)
	doclistobj.submit()
	
	return [d.fields for d in doclist]

@webnotes.whitelist()
def cancel(doctype, name):
	wrapper = webnotes.bean(doctype, name)
	wrapper.cancel()
	
	return [d.fields for d in wrapper.doclist]

@webnotes.whitelist()
def set_default(key, value, parent=None):
	"""set a user default value"""
	webnotes.conn.set_default(key, value, parent or webnotes.session.user)
	webnotes.clear_cache(user=webnotes.session.user)

@webnotes.whitelist()
def make_width_property_setter():
	doclist = json.loads(webnotes.form_dict.doclist)
	if doclist[0]["doctype"]=="Property Setter" and doclist[0]["property"]=="width":
		webnotes.bean(doclist).save()
