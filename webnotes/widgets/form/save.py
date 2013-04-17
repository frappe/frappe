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

@webnotes.whitelist()
def savedocs():
	"""save / submit / update doclist"""
	try:
		wrapper = webnotes.bean()
		wrapper.from_compressed(webnotes.form_dict.docs, webnotes.form_dict.docname)

		# action
		action = webnotes.form_dict.action
		if action=='Update': action='update_after_submit'
		getattr(wrapper, action.lower())()

		# update recent documents
		webnotes.user.update_recent(wrapper.doc.doctype, wrapper.doc.name)
		send_updated_docs(wrapper)

	except Exception, e:
		webnotes.msgprint(webnotes._('Did not save'))
		webnotes.errprint(webnotes.utils.getTraceback())
		raise e

@webnotes.whitelist()
def cancel(doctype=None, name=None):
	"""cancel a doclist"""
	try:
		wrapper = webnotes.bean(doctype, name)
		wrapper.cancel()
		send_updated_docs(wrapper)
		
	except Exception, e:
		webnotes.errprint(webnotes.utils.getTraceback())
		webnotes.msgprint(webnotes._("Did not cancel"))
		raise e
		
def send_updated_docs(wrapper):
	from load import add_file_list
	add_file_list(wrapper.doc.doctype, wrapper.doc.name, wrapper.doclist)
	
	webnotes.response['main_doc_name'] = wrapper.doc.name
	webnotes.response['doctype'] = wrapper.doc.doctype
	webnotes.response['docname'] = wrapper.doc.name
	webnotes.response['docs'] = wrapper.doclist