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

@webnotes.whitelist()
def getdoc():
	"""
	Loads a doclist for a given document. This method is called directly from the client.
	Requries "doctype", "name" as form variables.
	Will also call the "onload" method on the document.
	"""

	import webnotes
	from webnotes.utils import cint
	
	form = webnotes.form_dict
	doctype, docname = form.get('doctype'), form.get('name')
	prefix = cint(form.get('from_archive')) and 'arc' or 'tab'

	if not (doctype and docname):
		raise Exception, 'doctype and name required!'
	
	doclist = []
	# single
	doclist = load_single_doc(doctype, docname, (form.get('user') or webnotes.session['user']), prefix)
	
	# load doctype along with the doc
	if form.get('getdoctype'):
		import webnotes.model.doctype
		doclist += webnotes.model.doctype.get(doctype)

	# tag as archived
	if prefix == 'arc':
		doclist[0].__archived=1

	webnotes.response['docs'] = doclist

@webnotes.whitelist()
def getdoctype():
	"""load doctype"""
	import webnotes.model.doctype
	import webnotes.model.meta
	
	doclist = []
	
	dt = webnotes.form_dict.get('doctype')
	with_parent = webnotes.form_dict.get('with_parent')

	# with parent (called from report builder)
	if with_parent:
		parent_dt = webnotes.model.meta.get_parent_dt(dt)
		if parent_dt:
			doclist = webnotes.model.doctype.get(parent_dt)
			webnotes.response['parent_dt'] = parent_dt
	
	if not doclist:
		doclist = webnotes.model.doctype.get(dt)
	
	# if single, send the record too
	if doclist[0].issingle:
		doclist += webnotes.model.doc.get(dt)

	# load search criteria for reports (all)
	doclist +=get_search_criteria(dt)

	webnotes.response['docs'] = doclist

def load_single_doc(dt, dn, user, prefix):
	"""load doc and call onload methods"""
	import webnotes.model.code

	if not dn: dn = dt
	dl = webnotes.model.doc.get(dt, dn, prefix=prefix)

	# archive, done
	if prefix=='arc':
		return dl

	try:
		so, r = webnotes.model.code.get_server_obj(dl[0], dl), None
		if hasattr(so, 'onload'):
			r = webnotes.model.code.run_server_obj(so, 'onload')
		if hasattr(so, 'custom_onload'):
			r = webnotes.model.code.run_server_obj(so, 'custom_onload')
		if r: 
			webnotes.msgprint(r)
	except Exception, e:
		webnotes.errprint(webnotes.utils.getTraceback())
		webnotes.msgprint('Error in script while loading')
		raise e

	if dl and not dn.startswith('_'):
		webnotes.user.update_recent(dt, dn)

	# load search criteria ---- if doctype
	if dt=='DocType':
		dl += get_search_criteria(dt)

	return dl


def get_search_criteria(dt):
	"""bundle search criteria with doctype"""
	import webnotes.model.doc
	# load search criteria for reports (all)
	dl = []
	sc_list = webnotes.conn.sql("select name from `tabSearch Criteria` where doc_type = '%s' or parent_doc_type = '%s' and (disabled!=1 OR disabled IS NULL)" % (dt, dt))
	for sc in sc_list:
		if sc[0]:
			dl += webnotes.model.doc.get('Search Criteria', sc[0])
	return dl
