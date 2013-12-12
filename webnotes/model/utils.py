# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes, json
from webnotes import _
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

	docs = json.loads(docs)
	clist = []
	for d in docs['_vl']:
		doc = xzip(docs['_kl'][d[0]], d);
		clist.append(doc)
	return clist

def compress(doclist):
	"""
	   Compress a doclist before sending it to the client side. (Internally used by the request handler)

	"""
	docs = [isinstance(d, Document) and d.fields or d for d in doclist]

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

def delete_doc(doctype=None, name=None, doclist = None, force=0, ignore_doctypes=[], for_reload=False, ignore_permissions=False):
	"""
		Deletes a doc(dt, dn) and validates if it is not submitted and not linked in a live record
	"""
	import webnotes.model.meta

	# get from form
	if not doctype:
		doctype = webnotes.form_dict.get('dt')
		name = webnotes.form_dict.get('dn')
	
	if not doctype:
		webnotes.msgprint('Nothing to delete!', raise_exception =1)

	# already deleted..?
	if not webnotes.conn.exists(doctype, name):
		return

	if not for_reload:
		check_permission_and_not_submitted(doctype, name, ignore_permissions)
		
		run_on_trash(doctype, name, doclist)
		# check if links exist
		if not force:
			check_if_doc_is_linked(doctype, name)
		
	try:
		tablefields = webnotes.model.meta.get_table_fields(doctype)
		webnotes.conn.sql("delete from `tab%s` where name=%s" % (doctype, "%s"), name)
		for t in tablefields:
			if t[0] not in ignore_doctypes:
				webnotes.conn.sql("delete from `tab%s` where parent = %s" % (t[0], '%s'), name)
	except Exception, e:
		if e.args[0]==1451:
			webnotes.msgprint("Cannot delete %s '%s' as it is referenced in another record. You must delete the referred record first" % (doctype, name))
		
		raise
		
	# delete attachments
	from webnotes.utils.file_manager import remove_all
	remove_all(doctype, name)
		
	return 'okay'

def check_permission_and_not_submitted(doctype, name, ignore_permissions=False):
	# permission
	if not ignore_permissions and webnotes.session.user!="Administrator" and not webnotes.has_permission(doctype, "cancel"):
		webnotes.msgprint(_("User not allowed to delete."), raise_exception=True)

	# check if submitted
	if webnotes.conn.get_value(doctype, name, "docstatus") == 1:
		webnotes.msgprint(_("Submitted Record cannot be deleted")+": "+name+"("+doctype+")",
			raise_exception=True)

def run_on_trash(doctype, name, doclist):
	# call on_trash if required
	if doclist:
		bean = webnotes.bean(doclist)
	else:
		bean = webnotes.bean(doctype, name)
		
	bean.run_method("on_trash")

class LinkExistsError(webnotes.ValidationError): pass

def check_if_doc_is_linked(dt, dn, method="Delete"):
	"""
		Raises excption if the given doc(dt, dn) is linked in another record.
	"""
	from webnotes.model.rename_doc import get_link_fields
	link_fields = get_link_fields(dt)
	link_fields = [[lf['parent'], lf['fieldname'], lf['issingle']] for lf in link_fields]

	for link_dt, link_field, issingle in link_fields:
		if not issingle:
			item = webnotes.conn.get_value(link_dt, {link_field:dn}, 
				["name", "parent", "parenttype", "docstatus"], as_dict=True)
			
			if item and item.parent != dn and (method=="Delete" or 
					(method=="Cancel" and item.docstatus==1)):
				webnotes.msgprint(method + " " + _("Error") + ":"+\
					("%s (%s) " % (dn, dt)) + _("is linked in") + (" %s (%s)") % 
					(item.parent or item.name, item.parent and item.parenttype or link_dt),
					raise_exception=LinkExistsError)

def set_default(doc, key):
	if not doc.is_default:
		webnotes.conn.set(doc, "is_default", 1)
	
	webnotes.conn.sql("""update `tab%s` set `is_default`=0
		where `%s`=%s and name!=%s""" % (doc.doctype, key, "%s", "%s"), 
		(doc.fields.get(key), doc.name))
