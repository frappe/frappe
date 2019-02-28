# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document
from frappe.desk.form import assign_to

class AutoAssign(Document):
	def on_update(self): # pylint: disable=no-self-use
		frappe.cache().delete_value('auto_assign')

	def apply(self, doc):
		if self.safe_eval('assign_condition', doc):
			self.do_assignment(doc)

		# try clearing
		elif self.unassign_condition:
			self.clear_assignment(doc)

	def do_assignment(self, doc):
		user = self.get_user()

		assign_to.add(dict(
			assign_to = user,
			doctype = doc.get('doctype'),
			name = doc.get('name'),
			description = self.description
		))

		# set for reference in round robin
		self.db_set('last_user', user)

	def clear_assignment(self, doc):
		'''Clear assignments'''
		if self.safe_eval('unassign_condition', doc):
			assign_to.clear(doc.get('doctype'), doc.get('name'))

	def get_user(self):
		'''
		Get the next user for assignment
		'''
		if self.rule == 'Round Robin':
			return self.get_user_round_robin()
		elif self.rule == 'Load Balancing':
			return self.get_user_load_balancing()

	def get_user_round_robin(self):
		'''
		Get next user based on round robin
		'''

		# first time, or last in list, pick the first
		if not self.last_user or self.last_user == self.users[-1].user:
			return self.users[0].user

		# find out the next user in the list
		for i, d in enumerate(self.users):
			if self.last_user == d.user:
				return self.users[i+1].user

	def get_user_load_balancing(self):
		'''Assign to the user with least number of open assignments'''
		counts = []
		for d in self.users:
			counts.append(dict(
				user = d.user,
				count = frappe.db.count('ToDo', dict(
					reference_type = self.document_type,
					owner = d.user,
					status = "Open"))
			))

		# sort by dict value
		sorted_counts = sorted(counts, key = lambda k: k['count'])

		# pick the first user
		return sorted_counts[0].get('user')

	def safe_eval(self, fieldname, doc):
		try:
			return frappe.safe_eval(self.get(fieldname), None, doc)
		except Exception:
			# when assignment fails, don't block the document as it may be
			# a part of the email pulling
			frappe.msgprint(frappe._('Auto assignment failed'), indicator = 'orange')

def apply(doc, method):
	if frappe.flags.in_patch or frappe.flags.in_install:
		return

	auto_assigns = frappe.cache().get_value('auto_assign', get_auto_assigns)
	if doc.doctype in auto_assigns:
		frappe.get_doc('Auto Assign', doc.doctype).apply(doc.as_dict())

def get_auto_assigns():
	return [d.name for d in frappe.db.get_all('Auto Assign', dict(disabled = 0))]