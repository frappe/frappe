# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import hashlib
from frappe.model.document import Document
from frappe.utils import now, cint

class TestTransactionLog(unittest.TestCase):
	def before_insert(self):
		index = self.getcurrentindex()
		self.row_index = index
		self.timestamp = now()
		if index != 1:
			self.previous_hash = frappe.db.sql(
				"SELECT chaining_hash FROM `tabTransactionLog` WHERE row_index = {0}".format(index - 1))
		else:
			self.previous_hash = self.hash_line()
		self.transaction_hash = self.hash_line()
		self.chaining_hash = self.hash_chain()
		# if self.chaining_hash:
		# 	if self.reference_doctype == 'Sales Invoice':
		# 		frappe.db.sql("Update `tabSales Invoice` set chaining_hash ='{0}' where name = '{1}' ".format(self.chaining_hash, self.document_name))
		# 	else:
		# 		frappe.db.sql("Update `tabPayment Entry` set chaining_hash ='{0}' where name = '{1}' ".format(self.chaining_hash, self.document_name))

		self.name = self.chaining_hash
		self.checksum_version = "v1.0.0"

	def hash_line(self):
		sha = hashlib.sha256()
		sha.update(str(self.row_index) + str(self.timestamp) + str(self.data))
		return sha.hexdigest()

	def hash_chain(self):
		sha = hashlib.sha256()
		sha.update(str(self.transaction_hash) + str(self.previous_hash))
		return sha.hexdigest()

	def getcurrentindex(self):
		current = frappe.db.sql("SELECT `current` FROM tabSeries WHERE name='TRANSACTLOG' FOR UPDATE")
		if current and current[0][0] is not None:
			current = current[0][0]

			frappe.db.sql("UPDATE tabSeries SET current = current+1 where name='TRANSACTLOG'")
			current = cint(current) + 1
		else:
			frappe.db.sql("INSERT INTO tabSeries (name, current) VALUES ('TRANSACTLOG', 1)")
			current = 1
		return current

	def create_transaction_log(doctype, document, data):

		transaction_log = frappe.get_doc({
			"doctype": "TransactionLog",
			"reference_doctype": doctype,
			"document_name": document,
			"data": data
		}).insert(ignore_permissions=True)

