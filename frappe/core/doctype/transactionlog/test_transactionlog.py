# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals
import frappe
import unittest
import frappe.utils
from frappe.utils import cint
from frappe.core.doctype.transactionlog.transactionlog import create_transaction_log
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice
from erpnext.accounts.doctype.payment_entry.test_payment_entry import get_payment_entry
import hashlib

test_dependencies = ["Item"]

class TestTransactionLog(unittest.TestCase):
	def test_transaction_log_creation(self):

		if cint(frappe.conf.get("log_transactions")) == 1:
			s_invoice = create_sales_invoice()

			si_transactionlog = frappe.get_all("TransactionLog",filters={'reference_doctype':s_invoice.doctype,'document_name':s_invoice.name})
			self.assertTrue(si_transactionlog[0])

			p_entry = get_payment_entry("Sales Invoice", s_invoice.name, bank_account="_Test Bank - _TC")
			p_entry.paid_from = "Debtors - _TC"
			p_entry.reference_no = "Test"
			p_entry.reference_date = "2016-01-01"
			p_entry.insert()
			p_entry.submit()

			pe_transactionlog = frappe.get_all("TransactionLog",filters={'reference_doctype':p_entry.doctype,'document_name':p_entry.name})
			self.assertTrue(pe_transactionlog[0])

	def test_chaining_hash(self):

		if cint(frappe.conf.get("log_transactions")) == 1:
			transactionlogs = frappe.get_all("TransactionLog",fields=["name", "row_index", "transaction_hash", "chaining_hash"])
			sha = hashlib.sha256()
			sha.update(str(transactionlogs[-2].transaction_hash) + str(transactionlogs[-1].chaining_hash))

			self.assertTrue(sha.hexdigest()==transactionlogs[-2].chaining_hash)
