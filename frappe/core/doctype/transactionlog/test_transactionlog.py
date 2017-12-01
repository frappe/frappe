# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals
import frappe
import unittest
import frappe.utils
from frappe.core.doctype.transactionlog.transactionlog import create_transaction_log
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice
from erpnext.accounts.doctype.payment_entry.test_payment_entry import get_payment_entry

test_records = frappe.get_test_records('TransactionLog')

class TestTransactionLog(unittest.TestCase):

	def Testcreate_transaction_log(self):

		s_invoice = create_sales_invoice()

		p_entry = get_payment_entry("Sales Invoice", s_invoice.name, bank_account="_Test Bank - _TC")
		p_entry.paid_from = "Debtors - _TC"
		p_entry.insert()
		p_entry.submit()

		transactionlog = frappe.get_all("Transactionlog",
		filters={'reference_doctype':s_invoice.doctype,'document_name':s_invoice.name})
		if transactionlog:
			if transactionlog.chaining_hash is None:
				print(transactionlog.name, transactionlog.creation, transactionlog.document_name)
