# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

class TestAutoAssign(unittest.TestCase):
	def test_round_robin(self):


def get_auto_assign():
	if not frappe.db.exists('Auto Assign', 'Note'):
		auto_assign = frappe.get_doc(dict(
			doctype = 'Auto Assign',
			document_type = 'Note',
			assign_condition = 'public = 1',
			unassign_condition = 'public = 0',
			rule = 'Round Robin',
			users = [
				dict(user = 'test@example.com'),
				dict(user = 'test1@example.com'),
				dict(user = 'test2@example.com'),
			]
		)).insert()
	else:
		auto_assign = frappe.get_doc('Auto Assign', 'Note')

	return auto_assign
