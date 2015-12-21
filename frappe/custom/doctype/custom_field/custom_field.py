# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr
from frappe import _
import json
from frappe.model.document import Document

class CustomField(Document):
	def autoname(self):
		self.set_fieldname()
		self.name = self.dt + "-" + self.fieldname

	def set_fieldname(self):
		if not self.fieldname:
			if not self.label:
				frappe.throw(_("Label is mandatory"))
			# remove special characters from fieldname
			self.fieldname = filter(lambda x: x.isdigit() or x.isalpha() or '_',
				cstr(self.label).lower().replace(' ','_'))

	def validate(self):
		if not self.idx:
			self.idx = len(frappe.get_meta(self.dt).get("fields")) + 1

		if not self.fieldname:
			frappe.throw(_("Fieldname not set for Custom Field"))

	def on_update(self):
		frappe.clear_cache(doctype=self.dt)
		if not self.flags.ignore_validate:
			# validate field
			from frappe.core.doctype.doctype.doctype import validate_fields_for_doctype
			validate_fields_for_doctype(self.dt)

		# create property setter to emulate insert after
		if self.insert_after:
			self.set_property_setter_for_idx()

		# update the schema
		# if not frappe.flags.in_test:
		from frappe.model.db_schema import updatedb
		updatedb(self.dt)

	def on_trash(self):
		# delete property setter entries
		frappe.db.sql("""\
			DELETE FROM `tabProperty Setter`
			WHERE doc_type = %s
			AND field_name = %s""",
				(self.dt, self.fieldname))

		frappe.clear_cache(doctype=self.dt)

	def set_property_setter_for_idx(self):
		dt_meta = frappe.get_meta(self.dt)
		if not dt_meta.get_field(self.insert_after):
			frappe.throw(_("Insert After field '{0}' mentioned in Custom Field '{1}', does not exist")
				.format(self.insert_after, self.label), frappe.DoesNotExistError)
				
		if self.fieldname == self.insert_after:
			frappe.throw(_("Insert After cannot be set as {0}").format(dt_meta.get_label(self.insert_after)))

		frappe.db.sql("""\
			DELETE FROM `tabProperty Setter`
			WHERE doc_type = %s
			AND field_name = %s
			AND property = 'previous_field'""", (self.dt, self.fieldname))
		
		_idx = []
		field_order_changed = False
		
		existing_property_setter = frappe.db.get_value("Property Setter", 
			{"doc_type": self.dt, "property": "_idx"}, ["name", "value"], as_dict=1)
		
		# if no existsing property setter, build based on meta
		if not existing_property_setter:
			for df in sorted(dt_meta.get("fields"), key=lambda x: x.idx):
				_idx.append(df.fieldname)
			field_order_changed = True
		else:
			_idx = json.loads(existing_property_setter.value)
			
			# Delete existing property setter if field's order has been changed
			existing_idx = _idx.index(self.fieldname) if self.fieldname in _idx else None
			if existing_idx==None or _idx[existing_idx - 1] != self.insert_after:
				frappe.delete_doc("Property Setter", existing_property_setter.name)
				field_order_changed = True
				
		# Create new peroperty setter if order changed
		if _idx and field_order_changed:
			if self.fieldname in _idx:
				_idx.remove(self.fieldname)
			
			new_idx = (_idx.index(self.insert_after) + 1) if (self.insert_after in _idx) else len(_idx)
				
			_idx[new_idx] = self.fieldname

			frappe.make_property_setter({
				"doctype":self.dt,
				"doctype_or_field": "DocType",
				"fieldname": self.fieldname,
				"property": "_idx",
				"value": json.dumps(_idx),
				"property_type": "Text"
			}, validate_fields_for_doctype=False)

@frappe.whitelist()
def get_fields_label(doctype=None):
	return [{"value": df.fieldname or "", "label": _(df.label or "")} for df in frappe.get_meta(doctype).get("fields")]

def create_custom_field_if_values_exist(doctype, df):
	df = frappe._dict(df)
	if df.fieldname in frappe.db.get_table_columns(doctype) and \
		frappe.db.sql("""select count(*) from `tab{doctype}`
			where ifnull({fieldname},'')!=''""".format(doctype=doctype, fieldname=df.fieldname))[0][0]:

		create_custom_field(doctype, df)


def create_custom_field(doctype, df):
	if not frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": df.fieldname}):
		frappe.get_doc({
			"doctype":"Custom Field",
			"dt": doctype,
			"permlevel": df.get("permlevel") or 0,
			"label": df.get("label"),
			"fieldname": df.get("fieldname"),
			"fieldtype": df.get("fieldtype"),
			"options": df.get("options"),
			"insert_after": df.get("insert_after"),
			"print_hide": df.get("print_hide")
		}).insert()
