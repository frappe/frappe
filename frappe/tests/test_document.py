# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest

class TestDocument(unittest.TestCase):
	def test_get_return_empty_list_for_table_field_if_none(self):
		d = frappe.get_doc({"doctype":"User"})
		self.assertEquals(d.get("roles"), [])

	def test_load(self):
		d = frappe.get_doc("DocType", "User")
		self.assertEquals(d.doctype, "DocType")
		self.assertEquals(d.name, "User")
		self.assertEquals(d.allow_rename, 1)
		self.assertTrue(isinstance(d.fields, list))
		self.assertTrue(isinstance(d.permissions, list))
		self.assertTrue(filter(lambda d: d.fieldname=="email", d.fields))

	def test_load_single(self):
		d = frappe.get_doc("Website Settings", "Website Settings")
		self.assertEquals(d.name, "Website Settings")
		self.assertEquals(d.doctype, "Website Settings")
		self.assertTrue(d.disable_signup in (0, 1))

	def test_insert(self):
		d = frappe.get_doc({
			"doctype":"Event",
			"subject":"test-doc-test-event 1",
			"starts_on": "2014-01-01",
			"event_type": "Public"
		})
		d.insert()
		self.assertTrue(d.name.startswith("EV"))
		self.assertEquals(frappe.db.get_value("Event", d.name, "subject"),
			"test-doc-test-event 1")

		# test if default values are added
		self.assertEquals(d.send_reminder, 1)
		return d

	def test_insert_with_child(self):
		d = frappe.get_doc({
			"doctype":"Event",
			"subject":"test-doc-test-event 2",
			"starts_on": "2014-01-01",
			"event_type": "Public"
		})
		d.insert()
		self.assertTrue(d.name.startswith("EV"))
		self.assertEquals(frappe.db.get_value("Event", d.name, "subject"),
			"test-doc-test-event 2")

	def test_update(self):
		d = self.test_insert()
		d.subject = "subject changed"
		d.save()

		self.assertEquals(frappe.db.get_value(d.doctype, d.name, "subject"), "subject changed")

	def test_mandatory(self):
		frappe.delete_doc_if_exists("User", "test_mandatory@example.com")

		d = frappe.get_doc({
			"doctype": "User",
			"email": "test_mandatory@example.com",
		})
		self.assertRaises(frappe.MandatoryError, d.insert)

		d.set("first_name", "Test Mandatory")
		d.insert()
		self.assertEquals(frappe.db.get_value("User", d.name), d.name)

	def test_confict_validation(self):
		d1 = self.test_insert()
		d2 = frappe.get_doc(d1.doctype, d1.name)
		d1.save()
		self.assertRaises(frappe.TimestampMismatchError, d2.save)

	def test_confict_validation_single(self):
		d1 = frappe.get_doc("Website Settings", "Website Settings")
		d1.home_page = "test-web-page-1"

		d2 = frappe.get_doc("Website Settings", "Website Settings")
		d2.home_page = "test-web-page-1"

		d1.save()
		self.assertRaises(frappe.TimestampMismatchError, d2.save)

	def test_permission(self):
		frappe.set_user("Guest")
		self.assertRaises(frappe.PermissionError, self.test_insert)
		frappe.set_user("Administrator")

	def test_permission_single(self):
		frappe.set_user("Guest")
		d = frappe.get_doc("Website Settings", "Website Settigns")
		self.assertRaises(frappe.PermissionError, d.save)
		frappe.set_user("Administrator")

	def test_link_validation(self):
		frappe.delete_doc_if_exists("User", "test_link_validation@example.com")

		d = frappe.get_doc({
			"doctype": "User",
			"email": "test_link_validation@example.com",
			"first_name": "Link Validation",
			"roles": [
				{
					"role": "ABC"
				}
			]
		})
		self.assertRaises(frappe.LinkValidationError, d.insert)

		d.roles = []
		d.append("roles", {
			"role": "System Manager"
		})
		d.insert()

		self.assertEquals(frappe.db.get_value("User", d.name), d.name)

	def test_validate(self):
		d = self.test_insert()
		d.starts_on = "2014-01-01"
		d.ends_on = "2013-01-01"
		self.assertRaises(frappe.ValidationError, d.validate)
		self.assertRaises(frappe.ValidationError, d.run_method, "validate")
		self.assertRaises(frappe.ValidationError, d.save)

	def test_update_after_submit(self):
		d = self.test_insert()
		d.starts_on = "2014-09-09"
		self.assertRaises(frappe.UpdateAfterSubmitError, d.validate_update_after_submit)
		d.meta.get_field("starts_on").allow_on_submit = 1
		d.validate_update_after_submit()
		d.meta.get_field("starts_on").allow_on_submit = 0

		# when comparing date(2014, 1, 1) and "2014-01-01"
		d.reload()
		d.starts_on = "2014-01-01"
		d.validate_update_after_submit()

	def test_varchar_length(self):
		d = self.test_insert()
		d.subject = "abcde"*100
		self.assertRaises(frappe.CharacterLengthExceededError, d.save)

	def test_xss_filter(self):
		d = self.test_insert()

		# script
		xss = '<script>alert("XSS")</script>'
		escaped_xss = xss.replace('<', '&lt;').replace('>', '&gt;')
		d.subject += xss
		d.save()
		d.reload()

		self.assertTrue(xss not in d.subject)
		self.assertTrue(escaped_xss in d.subject)

		# onload
		xss = '<div onload="alert("XSS")">Test</div>'
		escaped_xss = '<div>Test</div>'
		d.subject += xss
		d.save()
		d.reload()

		self.assertTrue(xss not in d.subject)
		self.assertTrue(escaped_xss in d.subject)

		# css attributes
		xss = '<div style="something: doesn\'t work; color: red;">Test</div>'
		escaped_xss = '<div style="color: red;">Test</div>'
		d.subject += xss
		d.save()
		d.reload()

		self.assertTrue(xss not in d.subject)
		self.assertTrue(escaped_xss in d.subject)

	def test_link_count(self):
		from frappe.model.utils.link_count import update_link_count

		update_link_count()

		doctype, name = 'User', 'test@example.com'

		d = self.test_insert()
		d.ref_type = doctype
		d.ref_name = name

		link_count = frappe.cache().get_value('_link_count') or {}
		old_count = link_count.get((doctype, name)) or 0

		d.save()

		link_count = frappe.cache().get_value('_link_count') or {}
		new_count = link_count.get((doctype, name)) or 0

		self.assertEquals(old_count + 1, new_count)

		frappe.db.commit()
		before_update = frappe.db.get_value(doctype, name, 'idx')

		update_link_count()

		after_update = frappe.db.get_value(doctype, name, 'idx')

		self.assertEquals(before_update + new_count, after_update)

	def test_save_si_then_update_naming_series(self):
		si = frappe.get_doc(sales_invoice)
		si.save()
		self.assertEqual(frappe.db.get_value(si.doctype, si.name, 'naming_series'), '_T-Sales Invoice-')

		si.naming_series = 'TEST-'
		self.assertRaises(frappe.ValidationError, si.save)

	def test_save_pi_then_update_naming_series(self):
		pi = frappe.get_doc(purchase_invoice)
		pi.save()
		self.assertEqual(frappe.db.get_value(pi.doctype, pi.name, 'naming_series'), '_T-BILL')

		pi.naming_series = 'TEST-'
		self.assertRaises(frappe.ValidationError, pi.save)

sales_invoice = {
			"company": "_Test Company",
			"conversion_rate": 1.0,
			"currency": "INR",
			"customer": "_Test Customer",
			"customer_name": "_Test Customer",
			"debit_to": "_Test Receivable - _TC",
			"doctype": "Sales Invoice",
			"items": [
				{
					"amount": 500.0,
					"base_amount": 500.0,
					"base_rate": 500.0,
					"cost_center": "_Test Cost Center - _TC",
					"description": "138-CMS Shoe",
					"doctype": "Sales Invoice Item",
					"income_account": "Sales - _TC",
					"expense_account": "_Test Account Cost for Goods Sold - _TC",
					"item_name": "138-CMS Shoe",
					"parentfield": "items",
					"qty": 1.0,
					"rate": 500.0,
					"uom": "_Test UOM",
					"conversion_factor": 1,
					"stock_uom": "_Test UOM"
				}
			],
			"base_grand_total": 561.8,
			"grand_total": 561.8,
			"is_pos": 0,
			"naming_series": "_T-Sales Invoice-",
			"base_net_total": 500.0,
			"taxes": [
				{
					"account_head": "_Test Account VAT - _TC",
					"charge_type": "On Net Total",
					"description": "VAT",
					"doctype": "Sales Taxes and Charges",
					"parentfield": "taxes",
					"rate": 6
				},
				{
					"account_head": "_Test Account Service Tax - _TC",
					"charge_type": "On Net Total",
					"description": "Service Tax",
					"doctype": "Sales Taxes and Charges",
					"parentfield": "taxes",
					"rate": 6.36
				}
			],
			"plc_conversion_rate": 1.0,
			"price_list_currency": "INR",
			"sales_team": [
				{
					"allocated_percentage": 65.5,
					"doctype": "Sales Team",
					"parentfield": "sales_team",
					"sales_person": "_Test Sales Person 1"
				},
				{
					"allocated_percentage": 34.5,
					"doctype": "Sales Team",
					"parentfield": "sales_team",
					"sales_person": "_Test Sales Person 2"
				}
			],
			"selling_price_list": "_Test Price List",
			"territory": "_Test Territory"
		}

purchase_invoice = {
	"bill_no": "NA",
	"buying_price_list": "_Test Price List",
	"company": "_Test Company",
	"conversion_rate": 1,
	"credit_to": "_Test Payable - _TC",
	"currency": "INR",
	"doctype": "Purchase Invoice",
	"items": [
	{
		"amount": 500,
		"base_amount": 500,
		"base_rate": 50,
		"conversion_factor": 1.0,
		"cost_center": "_Test Cost Center - _TC",
		"doctype": "Purchase Invoice Item",
		"expense_account": "_Test Account Cost for Goods Sold - _TC",
		"item_code": "_Test Item Home Desktop 100",
		"item_name": "_Test Item Home Desktop 100",
		"item_tax_rate": "{\"_Test Account Excise Duty - _TC\": 10}",
		"parentfield": "items",
		"qty": 10,
		"rate": 50,
		"uom": "_Test UOM",
		"warehouse": "_Test Warehouse - _TC"
	},
	{
		"amount": 750,
		"base_amount": 750,
		"base_rate": 150,
		"conversion_factor": 1.0,
		"cost_center": "_Test Cost Center - _TC",
		"doctype": "Purchase Invoice Item",
		"expense_account": "_Test Account Cost for Goods Sold - _TC",
		"item_code": "_Test Item Home Desktop 200",
		"item_name": "_Test Item Home Desktop 200",
		"parentfield": "items",
		"qty": 5,
		"rate": 150,
		"uom": "_Test UOM",
		"warehouse": "_Test Warehouse - _TC"
	}
	],
	"grand_total": 0,
	"naming_series": "_T-BILL",
	"taxes": [
	{
		"account_head": "_Test Account Shipping Charges - _TC",
		"add_deduct_tax": "Add",
		"category": "Valuation and Total",
		"charge_type": "Actual",
		"cost_center": "_Test Cost Center - _TC",
		"description": "Shipping Charges",
		"doctype": "Purchase Taxes and Charges",
		"parentfield": "taxes",
		"tax_amount": 100
	},
	{
		"account_head": "_Test Account Customs Duty - _TC",
		"add_deduct_tax": "Add",
		"category": "Valuation",
		"charge_type": "On Net Total",
		"cost_center": "_Test Cost Center - _TC",
		"description": "Customs Duty",
		"doctype": "Purchase Taxes and Charges",
		"parentfield": "taxes",
		"rate": 10
	},
	{
		"account_head": "_Test Account Excise Duty - _TC",
		"add_deduct_tax": "Add",
		"category": "Total",
		"charge_type": "On Net Total",
		"cost_center": "_Test Cost Center - _TC",
		"description": "Excise Duty",
		"doctype": "Purchase Taxes and Charges",
		"parentfield": "taxes",
		"rate": 12
	},
	{
		"account_head": "_Test Account Education Cess - _TC",
		"add_deduct_tax": "Add",
		"category": "Total",
		"charge_type": "On Previous Row Amount",
		"cost_center": "_Test Cost Center - _TC",
		"description": "Education Cess",
		"doctype": "Purchase Taxes and Charges",
		"parentfield": "taxes",
		"rate": 2,
		"row_id": 3
	},
	{
		"account_head": "_Test Account S&H Education Cess - _TC",
		"add_deduct_tax": "Add",
		"category": "Total",
		"charge_type": "On Previous Row Amount",
		"cost_center": "_Test Cost Center - _TC",
		"description": "S&H Education Cess",
		"doctype": "Purchase Taxes and Charges",
		"parentfield": "taxes",
		"rate": 1,
		"row_id": 3
	},
	{
		"account_head": "_Test Account CST - _TC",
		"add_deduct_tax": "Add",
		"category": "Total",
		"charge_type": "On Previous Row Total",
		"cost_center": "_Test Cost Center - _TC",
		"description": "CST",
		"doctype": "Purchase Taxes and Charges",
		"parentfield": "taxes",
		"rate": 2,
		"row_id": 5
	},
	{
		"account_head": "_Test Account VAT - _TC",
		"add_deduct_tax": "Add",
		"category": "Total",
		"charge_type": "On Net Total",
		"cost_center": "_Test Cost Center - _TC",
		"description": "VAT",
		"doctype": "Purchase Taxes and Charges",
		"parentfield": "taxes",
		"rate": 12.5
	},
	{
		"account_head": "_Test Account Discount - _TC",
		"add_deduct_tax": "Deduct",
		"category": "Total",
		"charge_type": "On Previous Row Total",
		"cost_center": "_Test Cost Center - _TC",
		"description": "Discount",
		"doctype": "Purchase Taxes and Charges",
		"parentfield": "taxes",
		"rate": 10,
		"row_id": 7
	}
	],
	"posting_date": "2013-02-03",
	"supplier": "_Test Supplier",
	"supplier_name": "_Test Supplier"
}

