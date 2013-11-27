# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes
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

def set_default(doc, key):
	if not doc.is_default:
		webnotes.conn.set(doc, "is_default", 1)
	
	webnotes.conn.sql("""update `tab%s` set `is_default`=0
		where `%s`=%s and name!=%s""" % (doc.doctype, key, "%s", "%s"), 
		(doc.fields.get(key), doc.name))
