# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document

class test_virtual_1(Document):
	def db_insert(self):
		d = self.get_valid_dict(convert_dates_to_str=True)
		with open("data_file.json", "w+") as read_file:
			json.dump(d, read_file)

	def load_from_db(self):
		with open("data_file.json", "r") as read_file:
			d = json.load(read_file)
			super(Document, self).__init__(d)

	def db_update(self):
		frappe.msgprint("ok")
		d = self.get_valid_dict(convert_dates_to_str=True)
		with open("data_file.json", "w+") as read_file:
			json.dump(d, read_file)

	def get_list(self, args):
		with open("data_file.json", "r") as read_file:
			return [json.load(read_file)]
