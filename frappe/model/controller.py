# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils import flt, cint, cstr
from frappe.model.meta import get_field_precision
from frappe.model.document import Document

class EmptyTableError(frappe.ValidationError): pass

class DocListController(Document):
	def validate_value(self, fieldname, condition, val2, doc=None, raise_exception=None):
		"""check that value of fieldname should be 'condition' val2
			else throw exception"""
		error_condition_map = {
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

		if not doc:
			doc = self
		
		df = self.meta.get_field(fieldname, parent=doc.doctype)
		
		val1 = doc.get(fieldname)
		
		if df.fieldtype in ("Currency", "Float"):
			val1 = flt(val1, self.precision(df.fieldname, doc.parentfield or None))
			val2 = flt(val2, self.precision(df.fieldname, doc.parentfield or None))
		elif df.fieldtype in ("Int", "Check"):
			val1 = cint(val1)
			val2 = cint(val2)
		elif df.fieldtype in ("Data", "Text", "Small Text", "Long Text", 
			"Text Editor", "Select", "Link"):
				val1 = cstr(val1)
				val2 = cstr(val2)
		
		if not frappe.compare(val1, condition, val2):
			msg = _("Error") + ": "
			if doc.parentfield:
				msg += _("Row") + (" # %d: " % doc.idx)
			
			msg += _(self.meta.get_label(fieldname, parent=doc.doctype)) \
				+ " " + error_condition_map.get(condition, "") + " " + cstr(val2)
			
			# raise passed exception or True
			msgprint(msg, raise_exception=raise_exception or True)
			
	def validate_table_has_rows(self, parentfield, raise_exception=None):
		if not self.get(parentfield):
			label = self.meta.get_label(parentfield)
			msgprint(_("Error") + ": " + _(label) + " " + _("cannot be empty"),
				raise_exception=raise_exception or EmptyTableError)
			
	def round_floats_in(self, doc, fieldnames=None):
		if not fieldnames:
			fieldnames = [df.fieldname for df in self.meta.get({"doctype": "DocField", "parent": doc.doctype, 
				"fieldtype": ["in", ["Currency", "Float"]]})]
		
		for fieldname in fieldnames:
			doc.set(fieldname, flt(doc.get(fieldname), self.precision(fieldname, doc.parentfield)))
			
	def precision(self, fieldname, parentfield=None):
		if not isinstance(parentfield, basestring):
			parentfield = parentfield.parentfield
		
		if not hasattr(self, "_precision"):
			self._precision = frappe._dict({
				"default": cint(frappe.db.get_default("float_precision")) or 3,
				"options": {}
			})
		
		if self._precision.setdefault(parentfield or "main", {}).get(fieldname) is None:
			df = self.meta.get_field(fieldname, parentfield=parentfield)
			
			if df.fieldtype == "Currency" and df.options and not self._precision.options.get(df.options):
				self._precision.options[df.options] = get_field_precision(df, self)
			
			if df.fieldtype == "Currency":
				self._precision[parentfield or "main"][fieldname] = cint(self._precision.options.get(df.options)) or \
					self._precision.default
			elif df.fieldtype == "Float":
				self._precision[parentfield or "main"][fieldname] = self._precision.default
		
		return self._precision[parentfield or "main"][fieldname]