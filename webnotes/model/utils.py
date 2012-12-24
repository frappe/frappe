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
from webnotes.model.doc import Document
"""
Model utilities, unclassified functions
"""

def expand(docs):
	"""
		Expand a doclist sent from the client side. (Internally used by the request handler)
	"""
	def xzip(a,b):
		d = {}
		for i in range(len(a)):
			d[a[i]] = b[i]
		return d

	from webnotes.utils import load_json

	docs = load_json(docs)
	clist = []
	for d in docs['_vl']:
		doc = xzip(docs['_kl'][d[0]], d);
		clist.append(doc)
	return clist

def compress(doclist):
	"""
	   Compress a doclist before sending it to the client side. (Internally used by the request handler)

	"""
	if doclist and hasattr(doclist[0],'fields'):
		docs = [d.fields for d in doclist]
	else:
		docs = doclist

	kl, vl = {}, []
	forbidden = ['server_code_compiled']

	# scan for keys & values
	for d in docs:
		dt = d['doctype']
		if not (dt in kl.keys()):
			kl[dt] = ['doctype','localname','__oldparent','__unsaved']	

		# add client script for doctype, doctype due to ambiguity
		if dt=='DocType' and '__client_script' not in kl[dt]: 
			kl[dt].append('__client_script')

		for f in d.keys():
			if not (f in kl[dt]) and not (f in forbidden):
				# if key missing, then append
				kl[dt].append(f)

		# build values
		tmp = []
		for f in kl[dt]:
			v = d.get(f)
			if type(v)==long:
				v=int(v)
			tmp.append(v)

		vl.append(tmp)
	return {'_vl':vl,'_kl':kl}


def getlist(doclist, field):
	from webnotes.utils import cint
	l = []
	for d in doclist:
		if d.parentfield == field:
			l.append(d)
	l.sort(lambda a, b: cint(a.idx) - cint(b.idx))
	return l

def copy_doclist(doclist, no_copy = []):
	"""
      Save & return a copy of the given doclist
      Pass fields that are not to be copied in `no_copy`
	"""
	from webnotes.model.doc import Document

	cl = []

	# main doc
	c = Document(fielddata = doclist[0].fields.copy())

	# clear no_copy fields
	for f in no_copy:
		if c.fields.has_key(f):
			c.fields[f] = None

	c.name = None
	c.save(1)
	cl.append(c)

	# new parent name
	parent = c.name

	# children
	for d in doclist[1:]:
		c = Document(fielddata = d.fields.copy())
		c.name = None

		# clear no_copy fields
		for f in no_copy:
			if c.fields.has_key(f):
				c.fields[f] = None

		c.parent = parent
		c.save(1)
		cl.append(c)

	return cl

def getvaluelist(doclist, fieldname):
	"""
		Returns a list of values of a particualr fieldname from all Document object in a doclist
	"""
	l = []
	for d in doclist:
		l.append(d.fields[fieldname])
	return l

def delete_doc(doctype=None, name=None, doclist = None, force=0):
	"""
		Deletes a doc(dt, dn) and validates if it is not submitted and not linked in a live record
	"""
	import webnotes.model.meta
	sql = webnotes.conn.sql

	# get from form
	if not doctype:
		doctype = webnotes.form_dict.get('dt')
		name = webnotes.form_dict.get('dn')
	
	if not doctype:
		webnotes.msgprint('Nothing to delete!', raise_exception =1)

	# already deleted..?
	if not webnotes.conn.exists(doctype, name):
		return

	# permission
	if webnotes.session.user!="Administrator" and not webnotes.has_permission(doctype, "cancel"):
		webnotes.msgprint("User not allowed to delete.", raise_exception=1)

	tablefields = webnotes.model.meta.get_table_fields(doctype)
	
	# check if submitted
	d = webnotes.conn.sql("select docstatus from `tab%s` where name=%s" % (doctype, '%s'), name)
	if d and int(d[0][0]) == 1:
		webnotes.msgprint("Submitted Record '%s' '%s' cannot be deleted" % (doctype, name))
		raise Exception
	
	# call on_trash if required
	from webnotes.model.code import get_obj
	if doclist:
		obj = get_obj(doclist=doclist)
	else:
		obj = get_obj(doctype, name)

	if hasattr(obj,'on_trash'):
		obj.on_trash()
	
	if doctype=='DocType':
		webnotes.conn.sql("delete from `tabCustom Field` where dt = %s", name)
		webnotes.conn.sql("delete from `tabCustom Script` where dt = %s", name)
		webnotes.conn.sql("delete from `tabProperty Setter` where doc_type = %s", name)
		webnotes.conn.sql("delete from `tabSearch Criteria` where doc_type = %s", name)

	# check if links exist
	if not force:
		check_if_doc_is_linked(doctype, name)
	# remove tags
	from webnotes.widgets.tags import clear_tags
	clear_tags(doctype, name)
	
	try:
		webnotes.conn.sql("delete from `tab%s` where name='%s' limit 1" % (doctype, name))
		for t in tablefields:
			webnotes.conn.sql("delete from `tab%s` where parent = %s" % (t[0], '%s'), name)
	except Exception, e:
		if e.args[0]==1451:
			webnotes.msgprint("Cannot delete %s '%s' as it is referenced in another record. You must delete the referred record first" % (doctype, name))
		
		raise e
		
	return 'okay'

def check_if_doc_is_linked(dt, dn):
	"""
		Raises excption if the given doc(dt, dn) is linked in another record.
	"""
	sql = webnotes.conn.sql

	from webnotes.model.rename_doc import get_link_fields
	link_fields = get_link_fields(dt)
	link_fields = [[lf['parent'], lf['fieldname']] for lf in link_fields]

	for l in link_fields:
		link_dt, link_field = l
		issingle = sql("select issingle from tabDocType where name = '%s'" % link_dt)

		# no such doctype (?)
		if not issingle: continue
		
		if issingle[0][0]:
			item = sql("select doctype from `tabSingles` where field='%s' and value = '%s' and doctype = '%s' " % (link_field, dn, l[0]))
			if item:
				webnotes.msgprint("Cannot delete %s <b>%s</b> because it is linked in <b>%s</b>" % (dt, dn, item[0][0]), raise_exception=1)
			
		else:
			item = None
			try:
				# (ifnull(parent, '')='' or `%s`!=`parent`)
				# this condition ensures that it allows deletion when child table field references parent
				
				item = sql("select name, parent, parenttype from `tab%s` where `%s`='%s' and docstatus!=2 and (ifnull(parent, '')='' or `%s`!=`parent`) \
					limit 1" % (link_dt, link_field, dn, link_field), debug=1)

			except Exception, e:
				if e.args[0]==1146: pass
				else: raise e
			if item:
				webnotes.msgprint("Cannot delete %s <b>%s</b> because it is linked in %s <b>%s</b>" % (dt, dn, item[0][2] or link_dt, item[0][1] or item[0][0]), raise_exception=1)


def round_doc(doc, precision_map):
	from webnotes.utils import flt
	for fieldname, precision in precision_map.items():
		doc.fields[fieldname] = flt(doc.fields.get(fieldname), precision)

def set_default(doc, key):
	if not doc.is_default:
		webnotes.conn.set(doc, "is_default", 1)
	
	webnotes.conn.sql("""update `tab%s` set `is_default`=0
		where `%s`=%s and name!=%s""" % (doc.doctype, key, "%s", "%s"), 
		(doc.fields.get(key), doc.name))
		
		