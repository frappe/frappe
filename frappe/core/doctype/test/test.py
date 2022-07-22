# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.model.document import Document


class test(Document):
	def db_insert(self, *args, **kwargs):
		d = self.get_valid_dict(convert_dates_to_str=True)
		with open("data_file.json", "w+") as read_file:
			json.dump(d, read_file)

	def load_from_db(self):
		with open("data_file.json") as read_file:
			d = json.load(read_file)
			super(Document, self).__init__(d)

	def db_update(self, *args, **kwargs):
		d = self.get_valid_dict(convert_dates_to_str=True)
		with open("data_file.json", "w+") as read_file:
			json.dump(d, read_file)

	@staticmethod
	def get_list(args):
		with open("data_file.json") as read_file:
			return [frappe._dict(json.load(read_file))]

	@staticmethod
	def get_count(args):
		return 5

	@staticmethod
	def get_stats(args):
		# return []
		with open("data_file.json") as read_file:
			return [json.load(read_file)]
