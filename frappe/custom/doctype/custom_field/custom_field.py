# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe import _
from frappe.model import core_doctypes_list
from frappe.model.docfield import supports_translation
from frappe.model.document import Document
from frappe.query_builder.functions import IfNull
from frappe.utils import cstr, random_string


class CustomField(Document):
	def autoname(self):
		self.set_fieldname()
		self.name = self.dt + "-" + self.fieldname

	def set_fieldname(self):
		restricted = (
			"name",
			"parent",
			"creation",
			"modified",
			"modified_by",
			"parentfield",
			"parenttype",
			"file_list",
			"flags",
			"docstatus",
		)
		if not self.fieldname:
			label = self.label
			if not label:
				if self.fieldtype in ["Section Break", "Column Break", "Tab Break"]:
					label = self.fieldtype + "_" + str(random_string(5))
				else:
					frappe.throw(_("Label is mandatory"))

			# remove special characters from fieldname
			self.fieldname = "".join(
				[c for c in cstr(label).replace(" ", "_") if c.isdigit() or c.isalpha() or c == "_"]
			)
			self.fieldname = f"custom_{self.fieldname}"

		# fieldnames should be lowercase
		self.fieldname = self.fieldname.lower()

		if self.fieldname in restricted:
			self.fieldname = self.fieldname + "1"

	def before_insert(self):
		self.set_fieldname()

	def validate(self):
		# these imports have been added to avoid cyclical import, should fix in future
		from frappe.core.doctype.doctype.doctype import check_fieldname_conflicts
		from frappe.custom.doctype.customize_form.customize_form import CustomizeForm

		# don't always get meta to improve performance
		# setting idx is just an improvement, not a requirement
		if self.is_new() or self.insert_after == "append":
			meta = frappe.get_meta(self.dt, cached=False)
			fieldnames = [df.fieldname for df in meta.get("fields")]

			if self.is_new() and self.fieldname in fieldnames:
				frappe.throw(
					_("A field with the name {0} already exists in {1}").format(
						frappe.bold(self.fieldname), self.dt
					)
				)

			if self.insert_after == "append":
				self.insert_after = fieldnames[-1]

			if self.insert_after and self.insert_after in fieldnames:
				self.idx = fieldnames.index(self.insert_after) + 1

		if (
			not self.is_virtual
			and (doc_before_save := self.get_doc_before_save())
			and (old_fieldtype := doc_before_save.fieldtype) != self.fieldtype
			and not CustomizeForm.allow_fieldtype_change(old_fieldtype, self.fieldtype)
		):
			frappe.throw(
				_("Fieldtype cannot be changed from {0} to {1}").format(old_fieldtype, self.fieldtype)
			)

		if not self.fieldname:
			frappe.throw(_("Fieldname not set for Custom Field"))

		if self.get("translatable", 0) and not supports_translation(self.fieldtype):
			self.translatable = 0

		check_fieldname_conflicts(self)

	def on_update(self):
		# validate field
		if not self.flags.ignore_validate:
			from frappe.core.doctype.doctype.doctype import validate_fields_for_doctype

			validate_fields_for_doctype(self.dt)

		# clear cache and update the schema
		if not frappe.flags.in_create_custom_fields:
			frappe.clear_cache(doctype=self.dt)
			frappe.db.updatedb(self.dt)

	def on_trash(self):
		# check if Admin owned field
		if self.owner == "Administrator" and frappe.session.user != "Administrator":
			frappe.throw(
				_(
					"Custom Field {0} is created by the Administrator and can only be deleted through the Administrator account."
				).format(frappe.bold(self.label))
			)

		# delete property setter entries
		frappe.db.delete("Property Setter", {"doc_type": self.dt, "field_name": self.fieldname})

		# update doctype layouts
		doctype_layouts = frappe.get_all(
			"DocType Layout", filters={"document_type": self.dt}, pluck="name"
		)

		for layout in doctype_layouts:
			layout_doc = frappe.get_doc("DocType Layout", layout)
			for field in layout_doc.fields:
				if field.fieldname == self.fieldname:
					layout_doc.remove(field)
					layout_doc.save()
					break

		frappe.clear_cache(doctype=self.dt)

	def validate_insert_after(self, meta):
		if not meta.get_field(self.insert_after):
			frappe.throw(
				_(
					"Insert After field '{0}' mentioned in Custom Field '{1}', with label '{2}', does not exist"
				).format(self.insert_after, self.name, self.label),
				frappe.DoesNotExistError,
			)

		if self.fieldname == self.insert_after:
			frappe.throw(_("Insert After cannot be set as {0}").format(meta.get_label(self.insert_after)))


@frappe.whitelist()
def get_fields_label(doctype=None):
	meta = frappe.get_meta(doctype)

	if doctype in core_doctypes_list:
		return frappe.msgprint(_("Custom Fields cannot be added to core DocTypes."))

	if meta.custom:
		return frappe.msgprint(_("Custom Fields can only be added to a standard DocType."))

	return [
		{"value": df.fieldname or "", "label": _(df.label or "")}
		for df in frappe.get_meta(doctype).get("fields")
	]


def create_custom_field_if_values_exist(doctype, df):
	df = frappe._dict(df)
	if df.fieldname in frappe.db.get_table_columns(doctype) and frappe.db.count(
		dt=doctype, filters=IfNull(df.fieldname, "") != ""
	):
		create_custom_field(doctype, df)


def create_custom_field(doctype, df, ignore_validate=False, is_system_generated=True):
	df = frappe._dict(df)
	if not df.fieldname and df.label:
		df.fieldname = frappe.scrub(df.label)
	if not frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": df.fieldname}):
		custom_field = frappe.get_doc(
			{
				"doctype": "Custom Field",
				"dt": doctype,
				"permlevel": 0,
				"fieldtype": "Data",
				"hidden": 0,
				"is_system_generated": is_system_generated,
			}
		)
		custom_field.update(df)
		custom_field.flags.ignore_validate = ignore_validate
		custom_field.insert()
		return custom_field


def create_custom_fields(custom_fields, ignore_validate=False, update=True):
	"""Add / update multiple custom fields

	:param custom_fields: example `{'Sales Invoice': [dict(fieldname='test')]}`"""

	try:
		frappe.flags.in_create_custom_fields = True
		doctypes_to_update = set()

		if frappe.flags.in_setup_wizard:
			ignore_validate = True

		for doctypes, fields in custom_fields.items():
			if isinstance(fields, dict):
				# only one field
				fields = [fields]

			if isinstance(doctypes, str):
				# only one doctype
				doctypes = (doctypes,)

			for doctype in doctypes:
				doctypes_to_update.add(doctype)

				for df in fields:
					field = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": df["fieldname"]})
					if not field:
						try:
							df = df.copy()
							df["owner"] = "Administrator"
							create_custom_field(doctype, df, ignore_validate=ignore_validate)

						except frappe.exceptions.DuplicateEntryError:
							pass

					elif update:
						custom_field = frappe.get_doc("Custom Field", field)
						custom_field.flags.ignore_validate = ignore_validate
						custom_field.update(df)
						custom_field.save()

		for doctype in doctypes_to_update:
			frappe.clear_cache(doctype=doctype)
			frappe.db.updatedb(doctype)

	finally:
		frappe.flags.in_create_custom_fields = False


@frappe.whitelist()
def rename_fieldname(custom_field: str, fieldname: str):
	frappe.only_for("System Manager")

	field: CustomField = frappe.get_doc("Custom Field", custom_field)
	parent_doctype = field.dt
	old_fieldname = field.fieldname
	field.fieldname = fieldname
	field.set_fieldname()
	new_fieldname = field.fieldname

	if field.is_system_generated:
		frappe.throw(_("System Generated Fields can not be renamed"))
	if frappe.db.has_column(parent_doctype, fieldname):
		frappe.throw(_("Can not rename as column {0} is already present on DocType.").format(fieldname))
	if old_fieldname == new_fieldname:
		frappe.msgprint(_("Old and new fieldnames are same."), alert=True)
		return

	frappe.db.rename_column(parent_doctype, old_fieldname, new_fieldname)

	# Update in DB after alter column is successful, alter column will implicitly commit, so it's
	# best to commit change on field too to avoid any possible mismatch between two.
	field.db_set("fieldname", field.fieldname, notify=True)
	_update_fieldname_references(field, old_fieldname, new_fieldname)

	frappe.db.commit()
	frappe.clear_cache()


def _update_fieldname_references(
	field: CustomField, old_fieldname: str, new_fieldname: str
) -> None:
	# Passwords are stored in auth table, so column name needs to be updated there.
	if field.fieldtype == "Password":
		Auth = frappe.qb.Table("__Auth")
		frappe.qb.update(Auth).set(Auth.fieldname, new_fieldname).where(
			(Auth.doctype == field.dt) & (Auth.fieldname == old_fieldname)
		).run()

	# Update ordering reference.
	frappe.db.set_value(
		"Custom Field",
		{"insert_after": old_fieldname, "dt": field.dt},
		"insert_after",
		new_fieldname,
	)
