# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

""" This is a virtual doctype controller for test/demo purposes.

- It uses a JSON file on disk as "backend".
- Key is docname and value is the document itself.

Example:
{
	"doc1": {"name": "doc1", ...}
	"doc2": {"name": "doc2", ...}
}
"""
import json
import os

import frappe
from frappe.model.document import Document

DATA_FILE = "data_file.json"


def get_current_data() -> dict[str, dict]:
	"""Read data from disk"""
	if not os.path.exists(DATA_FILE):
		return {}

	with open(DATA_FILE) as f:
		return json.load(f)


def update_data(data: dict[str, dict]) -> None:
	"""Flush updated data to disk"""
	with open(DATA_FILE, "w+") as data_file:
		json.dump(data, data_file)


class test(Document):
	def db_insert(self, *args, **kwargs):
		d = self.get_valid_dict(convert_dates_to_str=True)

		data = get_current_data()
		data[d.name] = d

		update_data(data)

	def load_from_db(self):
		data = get_current_data()
		d = data.get(self.name)
		super(Document, self).__init__(d)

	def db_update(self, *args, **kwargs):
		# For this example insert and update are same operation,
		# it might be  different for you
		self.db_insert(*args, **kwargs)

	def delete(self):
		data = get_current_data()
		data.pop(self.name, None)
		update_data(data)

	@staticmethod
	def get_list(args):
		data = get_current_data()
		return [frappe._dict(doc) for name, doc in data.items()]

	@staticmethod
	def get_count(args):
		data = get_current_data()
		return len(data)

	@staticmethod
	def get_stats(args):
		return {}
