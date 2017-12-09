# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals
import frappe
import unittest
import frappe.utils
from frappe.utils import cint
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice
from erpnext.accounts.doctype.payment_entry.test_payment_entry import get_payment_entry
import hashlib

test_dependencies = ["Item"]

class TestTransactionLog(unittest.TestCase):
	def test_chaining_hash(self):

		if cint(frappe.conf.get("log_transactions")) == 1:
			transactionlogs = frappe.get_all("TransactionLog",fields=["name", "row_index", "transaction_hash", "chaining_hash"])

			if transactionlogs:
				sha = hashlib.sha256()
				sha.update(str(transactionlogs[-2].transaction_hash) + str(transactionlogs[-1].chaining_hash))

				self.assertTrue(sha.hexdigest()==transactionlogs[-2].chaining_hash)
