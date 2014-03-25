# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe, unittest, time

from frappe.model.document import Document

class TestDocument(unittest.TestCase):
	def test_load(self):
		d = Document("DocType", "User")
		self.assertEquals(d.doctype, "DocType")
		self.assertEquals(d.name, "User")
		self.assertEquals(d.allow_rename, 1)
		self.assertTrue(isinstance(d.fields, list))
		self.assertTrue(isinstance(d.permissions, list))
		self.assertTrue(filter(lambda d: d.fieldname=="email", d.fields))
		
	def test_load_single(self):
		d = Document("Website Settings", "Website Settings")
		self.assertEquals(d.name, "Website Settings")
		self.assertEquals(d.doctype, "Website Settings")
		self.assertTrue(d.disable_signup in (0, 1))
		
	def test_insert(self):
		d = Document({
			"doctype":"Event",
			"subject":"_Test Event 1",
			"starts_on": "2014-01-01",
			"event_type": "Public"
		})
		d.insert()
		self.assertTrue(d.name.startswith("EV"))
		self.assertEquals(frappe.db.get_value("Event", d.name, "subject"), 
			"_Test Event 1")
			
		# test if default values are added
		self.assertEquals(d.send_reminder, 1)
		return d
		
	def test_insert_with_child(self):
		d = Document({
			"doctype":"Event",
			"subject":"_Test Event 2",
			"starts_on": "2014-01-01",
			"event_type": "Public",
			"event_individuals": [
				{
					"person": "Administrator"
				}
			]
		})
		d.insert()
		self.assertTrue(d.name.startswith("EV"))
		self.assertEquals(frappe.db.get_value("Event", d.name, "subject"), 
			"_Test Event 2")
		
		d1 = Document("Event", d.name)
		self.assertTrue(d1.event_individuals[0].person, "Administrator")
		
	def test_update(self):
		d = self.test_insert()
		d.subject = "subject changed"
		d.save()
		
		self.assertEquals(frappe.db.get_value(d.doctype, d.name, "subject"), "subject changed")
		
	def test_mandatory(self):
		d = Document({
			"doctype": "User",
			"email": "test_mandatory@example.com",
		})
		self.assertRaises(frappe.MandatoryError, d.insert)
		
		d.set("first_name", "Test Mandatory")
		d.insert()
		self.assertEquals(frappe.db.get_value("User", d.name), d.name)
	
	def test_confict_validation(self):
		d1 = self.test_insert()
		d2 = Document(d1.doctype, d1.name)
		time.sleep(1)
		d1.save()
		self.assertRaises(frappe.TimestampMismatchError, d2.save)

	def test_confict_validation_single(self):
		d1 = Document("Website Settings", "Website Settings")
		d2 = Document("Website Settings", "Website Settings")
		time.sleep(1)
		d1.save()
		self.assertRaises(frappe.TimestampMismatchError, d2.save)
	
	def test_link_validation(self):
		d = Document({
			"doctype": "User",
			"email": "test_link_validation@example.com",
			"first_name": "Link Validation",
			"user_roles": [
				{
					"role": "ABC"
				}
			]
		})
		self.assertRaises(frappe.LinkValidationError, d.insert)
		d.user_roles = []
		d.set("user_roles", {
			"role": "System Manager"
		})
		d.insert()
		self.assertEquals(frappe.db.get_value("User", d.name), d.name)