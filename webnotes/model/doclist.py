# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt 

import webnotes
import webnotes.model
from webnotes.model.doc import Document

class DocList(list):
	"""DocList object as a wrapper around a list"""
	def get(self, filters, limit=0):
		"""pass filters as:
			{"key": "val", "key": ["!=", "val"],
			"key": ["in", "val"], "key": ["not in", "val"], "key": "^val",
			"key" : True (exists), "key": False (does not exist) }"""

		out = []
		
		for doc in self:
			d = isinstance(getattr(doc, "fields", None), dict) and doc.fields or doc
			add = True
			for f in filters:
				fval = filters[f]
				
				if fval is True:
					fval = ["not None", fval]
				elif fval is False:
					fval = ["None", fval]
				elif not isinstance(fval, list):
					if isinstance(fval, basestring) and fval.startswith("^"):
						fval = ["^", fval[1:]]
					else:
						fval = ["=", fval]
				
				if not webnotes.compare(d.get(f), fval[0], fval[1]):
					add = False
					break

			if add:
				out.append(doc)
				if limit and (len(out)-1)==limit:
					break
		
		return DocList(out)
		
	def get_distinct_values(self, fieldname):
		return list(set(map(lambda d: d.fields.get(fieldname), self)))

	def remove_items(self, filters):
		for d in self.get(filters):
			self.remove(d)

	def getone(self, filters):
		return self.get(filters, limit=1)[0]

	def copy(self):
		out = []
		for d in self:
			if isinstance(d, dict):
				fielddata = d
			else:
				fielddata = d.fields
			fielddata.update({"name": None})
			out.append(Document(fielddata=fielddata))
		return DocList(out)
		
	def get_item_value(self, d, name):
		if isinstance(d, dict):
			return d.get(name)
		else:
			return d.fields.get(name)
		
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
			doc = Document(fielddata=doc)
			
		self._prepare_doc(doc)

		super(DocList, self).append(doc)
		
	def extend(self, doclist):
		doclist = objectify(doclist)
		for doc in doclist:
			self._prepare_doc(doc)
		
		super(DocList, self).extend(doclist)
		
		return self
		
	def _prepare_doc(self, doc):
		if not doc.name:
			doc.fields["__islocal"] = 1
			doc.docstatus = 0
		if doc.parentfield:
			if not doc.parenttype:
				doc.parenttype = self[0].doctype
			if not doc.parent:
				doc.parent = self[0].name
			if not doc.idx:
				siblings = [int(self.get_item_value(d, "idx") or 0) for d in self.get({"parentfield": doc.parentfield})]
				doc.idx = (max(siblings) + 1) if siblings else 1
		
def objectify(doclist):
	from webnotes.model.doc import Document
	return map(lambda d: isinstance(d, Document) and d or Document(d), doclist)
