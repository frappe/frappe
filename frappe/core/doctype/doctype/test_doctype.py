# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
import random
import string
import unittest
from unittest.case import skipIf
from unittest.mock import patch

import frappe
from frappe.cache_manager import clear_doctype_cache
from frappe.core.doctype.doctype.doctype import (
	CannotIndexedError,
	DocType,
	DoctypeLinkError,
	HiddenAndMandatoryWithoutDefaultError,
	IllegalMandatoryError,
	InvalidFieldNameError,
	UniqueFieldnameError,
	WrongOptionsDoctypeLinkError,
	validate_links_table_fieldnames,
)
from frappe.core.doctype.rq_job.test_rq_job import wait_for_completion
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.desk.form.load import getdoc
from frappe.model.delete_doc import delete_controllers
from frappe.model.sync import remove_orphan_doctypes
from frappe.tests import IntegrationTestCase
from frappe.utils import get_table_name


class TestDocType(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_validate_name(self):
		self.assertRaises(frappe.NameError, new_doctype("_Some DocType").insert)
		self.assertRaises(frappe.NameError, new_doctype("8Some DocType").insert)
		self.assertRaises(frappe.NameError, new_doctype("Some (DocType)").insert)
		self.assertRaises(
			frappe.NameError,
			new_doctype("Some Doctype with a name whose length is more than 61 characters").insert,
		)
		for name in ("Some DocType", "Some_DocType", "Some-DocType"):
			if frappe.db.exists("DocType", name):
				frappe.delete_doc("DocType", name)

			doc = new_doctype(name).insert()
			doc.delete()

	@skipIf(
		frappe.conf.db_type == "sqlite",
		"Not for SQLite for now",
	)
	def test_making_sequence_on_change(self):
		frappe.delete_doc_if_exists("DocType", self._testMethodName)
		dt = new_doctype(self._testMethodName).insert(ignore_permissions=True)
		autoname = dt.autoname

		# change autoname
		dt.autoname = "autoincrement"
		dt.save()

		# check if name type has been changed
		self.assertEqual(
			frappe.db.sql(
				f"""select data_type FROM information_schema.columns
				where column_name = 'name' and table_name = 'tab{self._testMethodName}'"""
			)[0][0],
			"bigint",
		)

		if frappe.db.db_type == "mariadb":
			table_name = "information_schema.tables"
			conditions = f"table_type = 'sequence' and table_name = '{self._testMethodName}_id_seq'"
		else:
			table_name = "information_schema.sequences"
			conditions = f"sequence_name = '{self._testMethodName}_id_seq'"

		# check if sequence table is created
		self.assertTrue(
			frappe.db.sql(
				f"""select * from {table_name}
				where {conditions}"""
			)
		)

		# change the autoname/naming rule back to original
		dt.autoname = autoname
		dt.save()

		# check if name type has changed
		self.assertEqual(
			frappe.db.sql(
				f"""select data_type FROM information_schema.columns
				where column_name = 'name' and table_name = 'tab{self._testMethodName}'"""
			)[0][0],
			"varchar" if frappe.db.db_type == "mariadb" else "character varying",
		)

	def test_doctype_unique_constraint_dropped(self):
		if frappe.db.exists("DocType", "With_Unique"):
			frappe.delete_doc("DocType", "With_Unique")

		dt = new_doctype("With_Unique", unique=1)
		dt.insert()

		doc1 = frappe.new_doc("With_Unique")
		doc2 = frappe.new_doc("With_Unique")
		doc1.some_fieldname = "Something"
		doc1.name = "one"
		doc2.some_fieldname = "Something"
		doc2.name = "two"

		doc1.insert()
		self.assertRaises(frappe.UniqueValidationError, doc2.insert)
		frappe.db.rollback()

		dt.fields[0].unique = 0
		dt.save()

		doc2.insert()
		doc1.delete()
		doc2.delete()

	def test_validate_search_fields(self):
		doc = new_doctype("Test Search Fields")
		doc.search_fields = "some_fieldname"
		doc.insert()
		self.assertEqual(doc.name, "Test Search Fields")

		# check if invalid fieldname is allowed or not
		doc.search_fields = "some_fieldname_1"
		self.assertRaises(frappe.ValidationError, doc.save)

		# check if no value fields are allowed in search fields
		field = doc.append("fields", {})
		field.fieldname = "some_html_field"
		field.fieldtype = "HTML"
		field.label = "Some HTML Field"
		doc.search_fields = "some_fieldname,some_html_field"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_depends_on_fields(self):
		doc = new_doctype("Test Depends On", depends_on="eval:doc.__islocal == 0")
		doc.insert()

		# check if the assignment operation is allowed in depends_on
		field = doc.fields[0]
		field.depends_on = "eval:doc.__islocal = 0"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_all_depends_on_fields_conditions(self):
		import re

		docfields = frappe.get_all(
			"DocField",
			or_filters={
				"ifnull(depends_on, '')": ("!=", ""),
				"ifnull(collapsible_depends_on, '')": ("!=", ""),
				"ifnull(mandatory_depends_on, '')": ("!=", ""),
				"ifnull(read_only_depends_on, '')": ("!=", ""),
			},
			fields=[
				"parent",
				"depends_on",
				"collapsible_depends_on",
				"mandatory_depends_on",
				"read_only_depends_on",
				"fieldname",
				"fieldtype",
			],
		)

		pattern = r'[\w\.:_]+\s*={1}\s*[\w\.@\'"]+'
		for field in docfields:
			for depends_on in [
				"depends_on",
				"collapsible_depends_on",
				"mandatory_depends_on",
				"read_only_depends_on",
			]:
				condition = field.get(depends_on)
				if condition:
					self.assertFalse(re.match(pattern, condition))

	@unittest.skipUnless(
		os.access(frappe.get_app_path("frappe"), os.W_OK), "Only run if frappe app paths is writable"
	)
	def test_sync_field_order(self):
		import os

		from frappe.modules.import_file import get_file_path

		# create test doctype
		test_doctype = frappe.get_doc(
			{
				"doctype": "DocType",
				"module": "Core",
				"fields": [
					{"label": "Field 1", "fieldname": "field_1", "fieldtype": "Data"},
					{"label": "Field 2", "fieldname": "field_2", "fieldtype": "Data"},
					{"label": "Field 3", "fieldname": "field_3", "fieldtype": "Data"},
					{"label": "Field 4", "fieldname": "field_4", "fieldtype": "Data"},
				],
				"permissions": [{"role": "System Manager", "read": 1}],
				"name": "Test Field Order DocType",
				"__islocal": 1,
			}
		)

		path = get_file_path(test_doctype.module, test_doctype.doctype, test_doctype.name)
		initial_fields_order = ["field_1", "field_2", "field_3", "field_4"]

		frappe.delete_doc_if_exists("DocType", "Test Field Order DocType")
		if os.path.isfile(path):
			os.remove(path)

		try:
			frappe.flags.allow_doctype_export = 1
			test_doctype.save()

			# assert that field_order list is being created with the default order
			test_doctype_json = frappe.get_file_json(path)
			self.assertTrue(test_doctype_json.get("field_order"))
			self.assertEqual(len(test_doctype_json["fields"]), len(test_doctype_json["field_order"]))
			self.assertListEqual(
				[f["fieldname"] for f in test_doctype_json["fields"]], test_doctype_json["field_order"]
			)
			self.assertListEqual([f["fieldname"] for f in test_doctype_json["fields"]], initial_fields_order)
			self.assertListEqual(test_doctype_json["field_order"], initial_fields_order)

			# remove field_order to test reload_doc/sync/migrate is backwards compatible without field_order
			del test_doctype_json["field_order"]
			with open(path, "w+") as txtfile:
				txtfile.write(frappe.as_json(test_doctype_json))

			# assert that field_order is actually removed from the json file
			test_doctype_json = frappe.get_file_json(path)
			self.assertFalse(test_doctype_json.get("field_order"))

			# make sure that migrate/sync is backwards compatible without field_order
			frappe.reload_doctype(test_doctype.name, force=True)
			test_doctype.reload()

			# assert that field_order list is being created with the default order again
			test_doctype.save()
			test_doctype_json = frappe.get_file_json(path)
			self.assertTrue(test_doctype_json.get("field_order"))
			self.assertEqual(len(test_doctype_json["fields"]), len(test_doctype_json["field_order"]))
			self.assertListEqual(
				[f["fieldname"] for f in test_doctype_json["fields"]], test_doctype_json["field_order"]
			)
			self.assertListEqual([f["fieldname"] for f in test_doctype_json["fields"]], initial_fields_order)
			self.assertListEqual(test_doctype_json["field_order"], initial_fields_order)

			# reorder fields: swap row 1 and 3
			test_doctype.fields[0], test_doctype.fields[2] = test_doctype.fields[2], test_doctype.fields[0]
			for i, f in enumerate(test_doctype.fields):
				f.idx = i + 1

			# assert that reordering fields only affects `field_order` rather than `fields` attr
			test_doctype.save()
			test_doctype_json = frappe.get_file_json(path)
			self.assertListEqual([f["fieldname"] for f in test_doctype_json["fields"]], initial_fields_order)
			self.assertListEqual(
				test_doctype_json["field_order"], ["field_3", "field_2", "field_1", "field_4"]
			)

			# reorder `field_order` in the json file: swap row 2 and 4
			test_doctype_json["field_order"][1], test_doctype_json["field_order"][3] = (
				test_doctype_json["field_order"][3],
				test_doctype_json["field_order"][1],
			)
			with open(path, "w+") as txtfile:
				txtfile.write(frappe.as_json(test_doctype_json))

			# assert that reordering `field_order` from json file is reflected in DocType upon migrate/sync
			frappe.reload_doctype(test_doctype.name, force=True)
			test_doctype.reload()
			self.assertListEqual(
				[f.fieldname for f in test_doctype.fields], ["field_3", "field_4", "field_1", "field_2"]
			)

			# insert row in the middle and remove first row (field 3)
			test_doctype.append("fields", {"label": "Field 5", "fieldname": "field_5", "fieldtype": "Data"})
			test_doctype.fields[4], test_doctype.fields[3] = test_doctype.fields[3], test_doctype.fields[4]
			test_doctype.fields[3], test_doctype.fields[2] = test_doctype.fields[2], test_doctype.fields[3]
			test_doctype.remove(test_doctype.fields[0])
			for i, f in enumerate(test_doctype.fields):
				f.idx = i + 1

			test_doctype.save()
			test_doctype_json = frappe.get_file_json(path)
			self.assertListEqual(
				[f["fieldname"] for f in test_doctype_json["fields"]],
				["field_1", "field_2", "field_4", "field_5"],
			)
			self.assertListEqual(
				test_doctype_json["field_order"], ["field_4", "field_5", "field_1", "field_2"]
			)
		except Exception:
			raise
		finally:
			frappe.flags.allow_doctype_export = 0

	def test_unique_field_name_for_two_fields(self):
		doc = new_doctype("Test Unique Field")
		field_1 = doc.append("fields", {})
		field_1.fieldname = "some_fieldname_1"
		field_1.fieldtype = "Data"

		field_2 = doc.append("fields", {})
		field_2.fieldname = "some_fieldname_1"
		field_2.fieldtype = "Data"

		self.assertRaises(UniqueFieldnameError, doc.insert)

	def test_fieldname_is_not_name(self):
		doc = new_doctype("Test Name Field")
		field_1 = doc.append("fields", {})
		field_1.label = "Name"
		field_1.fieldtype = "Data"
		doc.insert()
		self.assertEqual(doc.fields[1].fieldname, "name1")
		doc.fields[1].fieldname = "name"
		self.assertRaises(InvalidFieldNameError, doc.save)

	def test_illegal_mandatory_validation(self):
		doc = new_doctype("Test Illegal mandatory")
		field_1 = doc.append("fields", {})
		field_1.fieldname = "some_fieldname_1"
		field_1.fieldtype = "Section Break"
		field_1.reqd = 1

		self.assertRaises(IllegalMandatoryError, doc.insert)

	def test_link_with_wrong_and_no_options(self):
		doc = new_doctype("Test link")
		field_1 = doc.append("fields", {})
		field_1.fieldname = "some_fieldname_1"
		field_1.fieldtype = "Link"

		self.assertRaises(DoctypeLinkError, doc.insert)

		field_1.options = "wrongdoctype"

		self.assertRaises(WrongOptionsDoctypeLinkError, doc.insert)

	def test_hidden_and_mandatory_without_default(self):
		doc = new_doctype("Test hidden and mandatory")
		field_1 = doc.append("fields", {})
		field_1.fieldname = "some_fieldname_1"
		field_1.fieldtype = "Data"
		field_1.reqd = 1
		field_1.hidden = 1

		self.assertRaises(HiddenAndMandatoryWithoutDefaultError, doc.insert)

	def test_field_can_not_be_indexed_validation(self):
		doc = new_doctype("Test index")
		field_1 = doc.append("fields", {})
		field_1.fieldname = "some_fieldname_1"
		field_1.fieldtype = "Long Text"
		field_1.search_index = 1

		self.assertRaises(CannotIndexedError, doc.insert)

	def test_cancel_link_doctype(self):
		import json

		from frappe.desk.form.linked_with import cancel_all_linked_docs, get_submitted_linked_docs

		# create doctype
		link_doc = new_doctype("Test Linked Doctype")
		link_doc.is_submittable = 1
		for data in link_doc.get("permissions"):
			data.submit = 1
			data.cancel = 1
		link_doc.insert()

		doc = new_doctype("Test Doctype")
		doc.is_submittable = 1
		field_2 = doc.append("fields", {})
		field_2.label = "Test Linked Doctype"
		field_2.fieldname = "test_linked_doctype"
		field_2.fieldtype = "Link"
		field_2.options = "Test Linked Doctype"
		for data in link_doc.get("permissions"):
			data.submit = 1
			data.cancel = 1
		doc.insert()

		# create doctype data
		data_link_doc = frappe.new_doc("Test Linked Doctype")
		data_link_doc.some_fieldname = "Data1"
		data_link_doc.insert()
		data_link_doc.save()
		data_link_doc.submit()

		data_doc = frappe.new_doc("Test Doctype")
		data_doc.some_fieldname = "Data1"
		data_doc.test_linked_doctype = data_link_doc.name
		data_doc.insert()
		data_doc.save()
		data_doc.submit()

		docs = get_submitted_linked_docs(link_doc.name, data_link_doc.name)
		dump_docs = json.dumps(docs.get("docs"))
		cancel_all_linked_docs(dump_docs)
		data_link_doc.cancel()
		data_doc.load_from_db()
		self.assertEqual(data_link_doc.docstatus, 2)
		self.assertEqual(data_doc.docstatus, 2)

		# delete doctype record
		data_doc.delete()
		data_link_doc.delete()

		# delete doctype
		link_doc.delete()
		doc.delete()
		frappe.db.commit()

	def test_ignore_cancelation_of_linked_doctype_during_cancel(self):
		import json

		from frappe.desk.form.linked_with import cancel_all_linked_docs, get_submitted_linked_docs

		# create linked doctype
		link_doc = new_doctype("Test Linked Doctype 1")
		link_doc.is_submittable = 1
		for data in link_doc.get("permissions"):
			data.submit = 1
			data.cancel = 1
		link_doc.insert()

		# create first parent doctype
		test_doc_1 = new_doctype("Test Doctype 1")
		test_doc_1.is_submittable = 1

		field_2 = test_doc_1.append("fields", {})
		field_2.label = "Test Linked Doctype 1"
		field_2.fieldname = "test_linked_doctype_a"
		field_2.fieldtype = "Link"
		field_2.options = "Test Linked Doctype 1"

		for data in test_doc_1.get("permissions"):
			data.submit = 1
			data.cancel = 1
		test_doc_1.insert()

		# crete second parent doctype
		doc = new_doctype("Test Doctype 2")
		doc.is_submittable = 1

		field_2 = doc.append("fields", {})
		field_2.label = "Test Linked Doctype 1"
		field_2.fieldname = "test_linked_doctype_a"
		field_2.fieldtype = "Link"
		field_2.options = "Test Linked Doctype 1"

		for data in link_doc.get("permissions"):
			data.submit = 1
			data.cancel = 1
		doc.insert()

		# create doctype data
		data_link_doc_1 = frappe.new_doc("Test Linked Doctype 1")
		data_link_doc_1.some_fieldname = "Data1"
		data_link_doc_1.insert()
		data_link_doc_1.save()
		data_link_doc_1.submit()

		data_doc_2 = frappe.new_doc("Test Doctype 1")
		data_doc_2.some_fieldname = "Data1"
		data_doc_2.test_linked_doctype_a = data_link_doc_1.name
		data_doc_2.insert()
		data_doc_2.save()
		data_doc_2.submit()

		data_doc = frappe.new_doc("Test Doctype 2")
		data_doc.some_fieldname = "Data1"
		data_doc.test_linked_doctype_a = data_link_doc_1.name
		data_doc.insert()
		data_doc.save()
		data_doc.submit()

		docs = get_submitted_linked_docs(link_doc.name, data_link_doc_1.name)
		dump_docs = json.dumps(docs.get("docs"))

		cancel_all_linked_docs(dump_docs, ignore_doctypes_on_cancel_all=["Test Doctype 2"])

		# checking that doc for Test Doctype 2 is not canceled
		self.assertRaises(frappe.LinkExistsError, data_link_doc_1.cancel)

		data_doc.load_from_db()
		data_doc_2.load_from_db()
		self.assertEqual(data_link_doc_1.docstatus, 2)

		# linked doc is canceled
		self.assertEqual(data_doc_2.docstatus, 2)

		# ignored doctype 2 during cancel
		self.assertEqual(data_doc.docstatus, 1)

		# delete doctype record
		data_doc.cancel()
		data_doc.delete()
		data_doc_2.delete()
		data_link_doc_1.delete()

		# delete doctype
		link_doc.delete()
		doc.delete()
		test_doc_1.delete()
		frappe.db.commit()

	def test_links_table_fieldname_validation(self):
		doc = new_doctype("Test Links Table Validation")

		# check valid data
		doc.append("links", {"link_doctype": "User", "link_fieldname": "first_name"})
		validate_links_table_fieldnames(doc)  # no error
		doc.links = []  # reset links table

		# check invalid doctype
		doc.append("links", {"link_doctype": "User2", "link_fieldname": "first_name"})
		self.assertRaises(InvalidFieldNameError, validate_links_table_fieldnames, doc)
		doc.links = []  # reset links table

		# check invalid fieldname
		doc.append("links", {"link_doctype": "User", "link_fieldname": "a_field_that_does_not_exists"})

		self.assertRaises(InvalidFieldNameError, validate_links_table_fieldnames, doc)

	def test_create_virtual_doctype(self):
		"""Test virtual DocType."""
		virtual_doc = new_doctype("Test Virtual Doctype")
		virtual_doc.is_virtual = 1
		virtual_doc.insert(ignore_if_duplicate=True)
		virtual_doc.reload()
		doc = frappe.get_doc("DocType", "Test Virtual Doctype")

		self.assertDictEqual(doc.as_dict(), virtual_doc.as_dict())
		self.assertEqual(doc.is_virtual, 1)
		self.assertFalse(frappe.db.table_exists("Test Virtual Doctype"))

	def test_create_virtual_doctype_as_child_table(self):
		"""Test virtual DocType as Child Table below a normal DocType."""
		frappe.delete_doc_if_exists("DocType", "Test Parent Virtual DocType", force=1)
		frappe.delete_doc_if_exists("DocType", "Test Virtual DocType as Child Table", force=1)

		virtual_doc = new_doctype("Test Virtual DocType as Child Table")
		virtual_doc.is_virtual = 1
		virtual_doc.istable = 1
		virtual_doc.insert(ignore_permissions=True)

		doc = frappe.get_doc("DocType", "Test Virtual DocType as Child Table")

		self.assertEqual(doc.is_virtual, 1)
		self.assertEqual(doc.istable, 1)
		self.assertFalse(frappe.db.table_exists("Test Virtual DocType as Child Table"))

		parent_doc = new_doctype("Test Parent Virtual DocType")
		parent_doc.append(
			"fields",
			{
				"fieldname": "virtual_child_table",
				"fieldtype": "Table",
				"options": "Test Virtual DocType as Child Table",
			},
		)
		self.assertRaises(frappe.exceptions.ValidationError, parent_doc.insert)
		parent_doc.is_virtual = 1
		parent_doc.insert(ignore_permissions=True)
		self.assertFalse(frappe.db.table_exists("Test Parent Virtual DocType"))

	def test_default_fieldname(self):
		fields = [
			{"label": "title", "fieldname": "title", "fieldtype": "Data", "default": "{some_fieldname}"}
		]
		dt = new_doctype("DT with default field", fields=fields)
		dt.insert()

		dt.delete()

	def test_autoincremented_doctype_transition(self):
		frappe.delete_doc_if_exists("DocType", "testy_autoinc_dt")
		dt = new_doctype("testy_autoinc_dt", autoname="autoincrement").insert(ignore_permissions=True)
		dt.autoname = "hash"

		dt.save(ignore_permissions=True)

		dt_data = frappe.get_doc({"doctype": dt.name, "some_fieldname": "test data"}).insert(
			ignore_permissions=True
		)

		dt.autoname = "autoincrement"

		try:
			dt.save(ignore_permissions=True)
		except frappe.ValidationError as e:
			self.assertEqual(
				e.args[0],
				"Can only change to/from Autoincrement naming rule when there is no data in the doctype",
			)
		else:
			self.fail(
				"""Shouldn't be possible to transition to/from autoincremented doctype
				when data is present in doctype"""
			)
		finally:
			# cleanup
			dt_data.delete(ignore_permissions=True)
			dt.delete(ignore_permissions=True)

	def test_json_field(self):
		"""Test json field."""
		import json

		json_doc = new_doctype(
			"Test Json Doctype",
			fields=[{"label": "json field", "fieldname": "test_json_field", "fieldtype": "JSON"}],
		)
		json_doc.insert()
		json_doc.save()
		doc = frappe.get_doc("DocType", "Test Json Doctype")
		for field in doc.fields:
			if field.fieldname == "test_json_field":
				self.assertEqual(field.fieldtype, "JSON")
				break

		doc = frappe.get_doc(
			{"doctype": "Test Json Doctype", "test_json_field": json.dumps({"hello": "world"})}
		)
		doc.insert()
		doc.save()

		test_json = frappe.get_doc("Test Json Doctype", doc.name)

		if isinstance(test_json.test_json_field, str):
			test_json.test_json_field = json.loads(test_json.test_json_field)

		self.assertEqual(test_json.test_json_field["hello"], "world")

	def test_no_delete_doc(self):
		self.assertRaises(frappe.ValidationError, frappe.delete_doc, "DocType", "Address")

	@unittest.skipUnless(
		os.access(frappe.get_app_path("frappe"), os.W_OK), "Only run if frappe app paths is writable"
	)
	@patch.dict(frappe.conf, {"developer_mode": 1})
	def test_export_types(self):
		"""Export python types."""
		import ast

		from frappe.types.exporter import TypeExporter

		def validate(code):
			ast.parse(code)

		doctype = new_doctype(custom=0).insert()

		exporter = TypeExporter(doctype)
		code = exporter.controller_path.read_text()
		validate(code)

		# regenerate and verify and file is same word to word.
		exporter.export_types()
		new_code = exporter.controller_path.read_text()
		validate(new_code)

		self.assertEqual(code, new_code)

		# Add fields and save

		fieldname = "test_type"
		doctype.append("fields", {"fieldname": fieldname, "fieldtype": "Int"})
		doctype.save()

		new_field_code = exporter.controller_path.read_text()
		validate(new_field_code)

		self.assertIn(fieldname, new_field_code)
		self.assertIn("Int", new_field_code)

		doctype.delete()
		frappe.db.commit()

	@unittest.skipUnless(
		os.access(frappe.get_app_path("frappe"), os.W_OK), "Only run if frappe app paths is writable"
	)
	@patch.dict(frappe.conf, {"developer_mode": 1})
	def test_custom_field_deletion(self):
		"""Custom child tables whose doctype doesn't exist should be auto deleted."""
		doctype = new_doctype(custom=0).insert().name
		child = new_doctype(custom=0, istable=1).insert().name

		field = "abc"
		create_custom_fields({doctype: [{"fieldname": field, "fieldtype": "Table", "options": child}]})

		frappe.delete_doc("DocType", child)
		self.assertFalse(frappe.get_meta(doctype).get_field(field))

	@unittest.skipUnless(
		os.access(frappe.get_app_path("frappe"), os.W_OK), "Only run if frappe app paths is writable"
	)
	@patch.dict(frappe.conf, {"developer_mode": 1})
	def test_delete_doctype_with_customization(self):
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter

		custom_field = "customfield"

		doctype = new_doctype(custom=0).insert().name

		# Create property setter and custom field
		field = "some_fieldname"
		make_property_setter(doctype, field, "default", "DELETETHIS", "Data")
		create_custom_fields({doctype: [{"fieldname": custom_field, "fieldtype": "Data"}]})

		# Create 1 record
		original_doc = frappe.get_doc(doctype=doctype, custom_field_name="wat").insert()
		self.assertEqual(original_doc.some_fieldname, "DELETETHIS")

		# delete doctype
		frappe.delete_doc("DocType", doctype)
		clear_doctype_cache(doctype)

		# "restore" doctype by inserting doctype with same schema again
		new_doctype(doctype, custom=0).insert()

		# Ensure basically same doctype getting "restored"
		restored_doc = frappe.get_last_doc(doctype)
		verify_fields = ["doctype", field, custom_field]
		for f in verify_fields:
			self.assertEqual(original_doc.get(f), restored_doc.get(f))

		# Check form load of restored doctype
		getdoc(doctype, restored_doc.name)

		# ensure meta - property setter
		self.assertEqual(frappe.get_meta(doctype).get_field(field).default, "DELETETHIS")
		frappe.delete_doc("DocType", doctype)

	@unittest.skipUnless(
		os.access(frappe.get_app_path("frappe"), os.W_OK), "Only run if frappe app paths is writable"
	)
	@patch.dict(frappe.conf, {"developer_mode": 1})
	def test_delete_orphaned_doctypes(self):
		doctype = new_doctype(custom=0).insert()
		frappe.db.commit()

		delete_controllers(doctype.name, doctype.module)
		job = frappe.enqueue(remove_orphan_doctypes)
		wait_for_completion(job)

		frappe.db.rollback()
		self.assertFalse(frappe.db.exists("DocType", doctype.name))

	def test_not_in_list_view_for_not_allowed_mandatory_field(self):
		doctype = new_doctype(
			fields=[
				{
					"fieldname": "cover_image",
					"fieldtype": "Attach Image",
					"label": "Cover Image",
					"reqd": 1,  # mandatory
				},
				{
					"fieldname": "book_name",
					"fieldtype": "Data",
					"label": "Book Name",
					"reqd": 1,  # mandatory
				},
			],
		).insert()

		self.assertFalse(doctype.fields[0].in_list_view)
		self.assertTrue(doctype.fields[1].in_list_view)
		frappe.delete_doc("DocType", doctype.name)

	def test_no_recursive_fetch(self):
		recursive_dt = new_doctype(
			fields=[
				{
					"label": "User",
					"fieldname": "user",
					"fieldtype": "Link",
					"fetch_from": "user.email",
				}
			],
		)
		self.assertRaises(frappe.ValidationError, recursive_dt.insert)

	def test_meta_serialization(self):
		doctype = new_doctype(
			fields=[{"fieldname": "some_fieldname", "fieldtype": "Data", "set_only_once": 1}],
			is_submittable=1,
		).insert()
		doc = frappe.new_doc(doctype.name, some_fieldname="something").insert()
		doc.save()
		doc.submit()
		frappe.get_meta(doctype.name).as_dict()

	def test_row_compression(self):
		if frappe.db.db_type != "mariadb":
			return

		compressed_dt = new_doctype(row_format="Compressed").insert().name
		dynamic_dt = new_doctype().insert().name

		information_schema = frappe.qb.Schema("information_schema")

		def get_format(dt):
			return (
				frappe.qb.from_(information_schema.tables)
				.select("row_format")
				.where(
					(information_schema.tables.table_schema == frappe.conf.db_name)
					& (information_schema.tables.table_name == get_table_name(dt))
				)
				.run()[0][0]
				.upper()
			)

		self.assertEqual(get_format(compressed_dt), "COMPRESSED")
		self.assertEqual(get_format(dynamic_dt), "DYNAMIC")


def new_doctype(
	name: str | None = None,
	unique: bool = False,
	depends_on: str = "",
	fields: list[dict] | None = None,
	custom: bool = True,
	default: str | None = None,
	**kwargs,
) -> "DocType":
	if not name:
		# Test prefix is required to avoid coverage
		name = "Test " + "".join(random.sample(string.ascii_lowercase, 10))

	doc = frappe.get_doc(
		{
			"doctype": "DocType",
			"module": "Core",
			"custom": custom,
			"fields": [
				{
					"label": "Some Field",
					"fieldname": "some_fieldname",
					"fieldtype": "Data",
					"unique": unique,
					"default": default,
					"depends_on": depends_on,
				}
			],
			"permissions": [
				{
					"role": "System Manager",
					"read": 1,
				}
			],
			"name": name,
			**kwargs,
		}
	)

	if fields and len(fields) > 0:
		doc.set("fields", fields)

	return doc
