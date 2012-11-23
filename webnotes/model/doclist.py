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

import webnotes
import webnotes.model
from webnotes.model.doc import Document

class DocList(list):
	"""DocList object as a wrapper around a list"""	
	def get(self, filters, limit=0):
		"""pass filters as:
			{"key": "val", "key": ["!=", "val"],
			"key": ["in", "val"], "key": ["not in", "val"], "key": "^val"}"""
		# map reverse operations to set add = False
		import operator
		ops_map = {
			"!=": lambda (a, b): operator.ne(a, b),
			"in": lambda (a, b): operator.contains(b, a),
			"not in": lambda (a, b): not operator.contains(b, a)
		}
			
		out = []
		
		for doc in self:
			d = isinstance(getattr(doc, "fields", None), dict) and doc.fields or doc
			add = True
			for f in filters:
				fval = filters[f]
					
				if isinstance(fval, list):
					if fval[0] in ops_map and not ops_map[fval[0]]((d.get(f), fval[1])):
						add = False
						break
				elif isinstance(fval, basestring) and fval.startswith("^"):
					if not (d.get(f) or "").startswith(fval[1:]):
						add = False
						break
				elif d.get(f)!=fval:
					add = False
					break

			if add:
				out.append(doc)
				if limit and (len(out)-1)==limit:
					break
		
		return DocList(out)

	def getone(self, filters):
		return self.get(filters, limit=1)[0]

	def extend(self, n):
		list.extend(self, n)
		return self
		
	def copy(self):
		out = []
		for d in self:
			out.append(Document(d))
		return DocList(out)
		
	def filter_valid_fields(self):
		import webnotes.model
		fieldnames = {}
		for d in self:
			remove = []
			for f in d:
				if f not in fieldnames.setdefault(d.doctype,
						webnotes.model.get_fieldnames(d.doctype)):
					remove.append(f)
			for f in remove:
				del d[f]
				
	def append(self, doc):
		if not isinstance(doc, Document):
			doc = Document(doc)
			
		self._prepare_doc(doc)

		super(DocList, self).append(doc)
		
	def extend(self, doclist):
		doclist = objectify(doclist)
		for doc in doclist:
			self._prepare_doc(doc)
		
		super(DocList, self).extend(doclist)
		
	def _prepare_doc(self, doc):
		if not doc.name:
			doc.fields["__islocal"] = 1
		if doc.parentfield:
			if not doc.parenttype:
				doc.parenttype = self[0].doctype
			if not doc.parent:
				doc.parent = self[0].name

def load(doctype, name):	
	# load main doc
	return objectify(load_doclist(doctype, name))

def load_doclist(doctype, name):
	doclist = DocList([load_main(doctype, name)])
	
	# load children
	table_fields = map(lambda f: (f.options, name, f.fieldname, doctype),
		webnotes.conn.get_table_fields(doctype))

	for args in table_fields:
		children = load_children(*args)
		if children: doclist += children
		
	return doclist

def load_main(doctype, name):
	"""retrieves doc from database"""
	if webnotes.conn.is_single(doctype):
		doc = webnotes.conn.sql("""select field, value from `tabSingles`
			where doctype=%s""", doctype, as_list=1)
		doc = dict(doc)
		doc["name"] = doctype
	else:
		doc  = webnotes.conn.sql("""select * from `tab%s` where name = %s""" % \
			(doctype, "%s"), name, as_dict=1)
		if not doc:
			raise NameError, """%s: "%s" does not exist""" % (doctype, name)
		doc = doc[0]

	doc["doctype"] = doctype
	return doc

def load_children(options, parent, parentfield, parenttype):
	"""load children based on options, parentfield, parenttype and parent"""
	options = options.split("\n")[0].strip()
		
	return webnotes.conn.sql("""select *, "%s" as doctype from `tab%s` where parent = %s 
		and parentfield = %s and parenttype = %s order by idx""" % (options, options, "%s", "%s", "%s"),
		(parent, parentfield, parenttype), as_dict=1)
		
def objectify(doclist):
	from webnotes.model.doc import Document
	return map(lambda d: isinstance(d, Document) and d or Document(d), doclist)
