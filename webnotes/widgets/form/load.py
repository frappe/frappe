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
import webnotes, json
import webnotes.model.doc
import webnotes.utils

@webnotes.whitelist()
def getdoc(doctype, name, user=None):
	"""
	Loads a doclist for a given document. This method is called directly from the client.
	Requries "doctype", "name" as form variables.
	Will also call the "onload" method on the document.
	"""

	import webnotes
	
	if not (doctype and name):
		raise Exception, 'doctype and name required!'
	
	doclist = []
	# single
	doclist = load_single_doc(doctype, name, user or webnotes.session.user)
	
	webnotes.response['docs'] = doclist

@webnotes.whitelist()
def getdoctype(doctype, with_parent=False, cached_timestamp=None):
	"""load doctype"""
	import webnotes.model.doctype
	import webnotes.model.meta
	
	doclist = []
	
	# with parent (called from report builder)
	if with_parent:
		parent_dt = webnotes.model.meta.get_parent_dt(doctype)
		if parent_dt:
			doclist = webnotes.model.doctype.get(parent_dt, processed=True)
			webnotes.response['parent_dt'] = parent_dt
	
	if not doclist:
		doclist = webnotes.model.doctype.get(doctype, processed=True)
	
	if cached_timestamp and doclist[0].modified==cached_timestamp:
		return "use_cache"
	
	webnotes.response['docs'] = doclist

def load_single_doc(dt, dn, user):
	"""load doc and call onload methods"""
	# ----- REPLACE BY webnotes.client.get ------

	if not dn: dn = dt

	if not webnotes.conn.exists(dt, dn):
		return None

	try:
		dl = webnotes.bean(dt, dn).doclist
		# add file list
		add_file_list(dt, dn, dl)
		add_comments(dt, dn, dl)
		add_assignments(dt, dn, dl)
		
	except Exception, e:
		webnotes.errprint(webnotes.utils.getTraceback())
		webnotes.msgprint('Error in script while loading')
		raise e

	if dl and not dn.startswith('_'):
		webnotes.user.update_recent(dt, dn)

	return dl
	
def add_file_list(dt, dn, dl):
	file_list = {}
	for f in webnotes.conn.sql("""select name, file_name, file_url from
		`tabFile Data` where attached_to_name=%s and attached_to_doctype=%s""", 
			(dn, dt), as_dict=True):
		file_list[f.file_url or f.file_name] = f.name

	if file_list:
		dl[0].file_list = json.dumps(file_list)
		
def add_comments(dt, dn, dl, limit=20):
	cl = webnotes.conn.sql("""select name, comment, comment_by, creation from `tabComment` 
		where comment_doctype=%s and comment_docname=%s 
		order by creation desc limit %s""" % ('%s','%s', limit), (dt, dn), as_dict=1)
		
	dl[0].fields["__comments"] = json.dumps(cl)
	
def add_assignments(dt, dn, dl):
	cl = webnotes.conn.sql_list("""select owner from `tabToDo`
		where reference_type=%(doctype)s and reference_name=%(name)s
		order by modified desc limit 5""", {
			"doctype": dt,
			"name": dn
		})
		
	dl[0].fields["__assign_to"] = json.dumps(cl)