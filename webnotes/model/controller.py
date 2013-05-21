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
from webnotes import msgprint, _
from webnotes.utils import flt, cint, cstr
from webnotes.model.meta import get_field_precision

error_coniditon_map = {
	"=": "!=",
	"!=": "=",
	"<": ">=",
	">": "<=",
	">=": "<",
	"<=": ">",
	"in": _("not in"),
	"not in": _("in"),
	"^": _("cannot start with"),
}

class DocListController(object):
	def __init__(self, doc, doclist):
		self.doc, self.doclist = doc, doclist
		
		if hasattr(self, "setup"):
			self.setup()
	
	@property
	def meta(self):
		if not hasattr(self, "_meta"):
			self._meta = webnotes.get_doctype(self.doc.doctype)
		return self._meta
		
	def validate_value(self, fieldname, condition, val2, doc=None, raise_exception=None):
		"""check that value of fieldname should be 'condition' val2
			else throw exception"""
		if not doc:
			doc = self.doc
		
		df = self.meta.get_field(fieldname, parent=doc.doctype)
		
		val1 = doc.fields.get(fieldname)
		if df.fieldtype in ("Currency", "Float"):
			val1 = flt(val1)
		elif df.fieldtype in ("Int", "Check"):
			val1 = cint(val1)
		
		if not webnotes.compare(val1, condition, val2):
			msg = _("Error: ")
			if doc.parentfield:
				msg += _("Row") + (" # %d: " % doc.idx)
			
			msg += _(self.meta.get_label(fieldname, parent=doc.doctype)) \
				+ " " + error_coniditon_map.get(condition, "") + " " + cstr(val2)
			
			# raise passed exception or True
			msgprint(msg, raise_exception=raise_exception or True)
			
	def round_floats_in(self, doc, fieldnames=None):
		if not fieldnames:
			fieldnames = [df.fieldname for df in self.meta.get({"doctype": "DocField", "parent": doc.doctype, 
				"fieldtype": ["in", ["Currency", "Float"]]})]
		
		for fieldname in fieldnames:
			doc.fields[fieldname] = flt(doc.fields.get(fieldname), self.precision(fieldname, doc.parentfield))
			
	def _process(self, parentfield):
		from webnotes.model.doc import Document
		if isinstance(parentfield, Document):
			parentfield = parentfield.parentfield
			
		elif isinstance(parentfield, dict):
			parentfield = parentfield.get("parentfield")
			
		return parentfield

	def precision(self, fieldname, parentfield=None):
		parentfield = self._process(parentfield)
		
		if not hasattr(self, "_precision"):
			self._precision = webnotes._dict({
				"default": cint(webnotes.conn.get_default("float_precision")) or 6,
				"options": {}
			})
		
		if self._precision.setdefault(parentfield or "main", {}).get(fieldname) is None:
			df = self.meta.get_field(fieldname, parentfield=parentfield)
			
			if df.fieldtype == "Currency" and df.options and not self._precision.options.get(df.options):
				self._precision.options[df.options] = get_field_precision(df, self.doc)
			
			self._precision[parentfield or "main"][fieldname] = cint(self._precision.options.get(df.options)) or \
				self._precision.default
		
		return self._precision[parentfield or "main"][fieldname]