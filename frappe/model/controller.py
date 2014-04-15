# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils import flt, cint, cstr
from frappe.model.meta import get_field_precision
from frappe.model.document import Document

class DocListController(Document):
	def __init__(self, arg1, arg2=None):
		super(DocListController, self).__init__(arg1, arg2)
		if hasattr(self, "setup"):
			self.setup()

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

		df = doc.meta.get_field(fieldname)

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
			label = doc.meta.get_label(fieldname)
			condition_str = error_condition_map.get(condition, "")
			if doc.parentfield:
				msg = _("Incorrect value in row {0}: {1} must be {2} {3}".format(doc.idx, label, condition_str, val2))
			else:
				msg = _("Incorrect value: {1} must be {2} {3}".format(label, condition_str, val2))

			# raise passed exception or True
			msgprint(msg, raise_exception=raise_exception or True)

	def validate_table_has_rows(self, parentfield, raise_exception=None):
		if not (isinstance(self.get(parentfield), list) and len(self.get(parentfield)) > 0):
			label = self.meta.get_label(parentfield)
			frappe.throw(_("Table {0} cannot be empty").format(label), raise_exception or frappe.EmptyTableError)

	def round_floats_in(self, doc, fieldnames=None):
		if not fieldnames:
			fieldnames = [df.fieldname for df in doc.meta.get("fields",
				{"fieldtype": ["in", ["Currency", "Float"]]})]

		for fieldname in fieldnames:
			doc.set(fieldname, flt(doc.get(fieldname), self.precision(fieldname, doc.parentfield)))

	def precision(self, fieldname, parentfield=None):
		if parentfield and not isinstance(parentfield, basestring):
			parentfield = parentfield.parentfield

		if not hasattr(self, "_precision"):
			self._precision = frappe._dict({
				"default": cint(frappe.db.get_default("float_precision")) or 3,
				"options": {}
			})

		if self._precision.setdefault(parentfield or "main", {}).get(fieldname) is None:
			meta = frappe.get_meta(self.meta.get_field(parentfield).options if parentfield else self.doctype)
			df = meta.get_field(fieldname)

			if df.fieldtype == "Currency" and df.options and not self._precision.options.get(df.options):
				self._precision.options[df.options] = get_field_precision(df, self)

			if df.fieldtype == "Currency":
				self._precision[parentfield or "main"][fieldname] = cint(self._precision.options.get(df.options)) or \
					self._precision.default
			elif df.fieldtype == "Float":
				self._precision[parentfield or "main"][fieldname] = self._precision.default

		return self._precision[parentfield or "main"][fieldname]
