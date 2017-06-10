# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors

from __future__ import unicode_literals

import unittest, frappe

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


class TestClient(unittest.TestCase):
	def test_set_value(self):
		todo = frappe.get_doc(dict(doctype='ToDo', description='test')).insert()
		frappe.set_value('ToDo', todo.name, 'description', 'test 1')
		self.assertEquals(frappe.get_value('ToDo', todo.name, 'description'), 'test 1')

		frappe.set_value('ToDo', todo.name, {'description': 'test 2'})
		self.assertEquals(frappe.get_value('ToDo', todo.name, 'description'), 'test 2')

	def test_set_value_si_naming_series(self):
		si = frappe.get_doc(sales_invoice)
		if not frappe.db.exists("Sales Invoice", si.name):
			si.insert()
		self.assertRaises(
			frappe.ValidationError,
			frappe.set_value,
			doctype='Sales Invoice', docname=si.name, fieldname='naming_series', value='TEST-'
		)

	def test_set_value_pi_naming_series(self):
		pi = frappe.get_doc(purchase_invoice)
		if not frappe.db.exists("Purchase Invoice", pi.name):
			pi.insert()
		self.assertRaises(
			frappe.ValidationError,
			frappe.set_value,
			doctype='Purchase Invoice', docname=pi.name, fieldname='naming_series', value='TEST-'
		)