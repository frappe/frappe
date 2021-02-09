# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
"""
"""
import frappe

class Tenant:
	def __init__(self, id, name, status, created, modified):
		self.id = id
		self.name = name
		self.status = status
		self.created = created
		self.modified = modified

	@classmethod
	def new(cls, name):
		"""Creates a new tenant.
		"""
		row = frappe.db.sql("insert into `tabTenant` (`name`) values (%s)", name, auto_commit=1)
		return cls.find(name)

	@classmethod
	def find(cls, name):
		rows = frappe.db.sql("select * from `tabTenant` where name=%s limit 1", name, as_dict=True)
		return rows and cls.from_row(rows[0])

	@classmethod
	def atleast_one_exist(cls):
		rows = frappe.db.sql("select * from `tabTenant` limit 1", as_dict=True)
		return bool(rows)

	@classmethod
	def from_row(cls, row):
		return cls(row['id'], row['name'], row['status'], row['created'], row['modified'])
