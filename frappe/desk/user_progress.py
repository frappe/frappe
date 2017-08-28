# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe

@frappe.whitelist()
def get_user_progress_slides():
	'''
		Return user progress slides for the desktop (called via `get_user_progress_slides` hook)
	'''
	slides = []
	for fn in frappe.get_hooks('get_user_progress_slides'):
		slides += frappe.get_attr(fn)()

	return slides

@frappe.whitelist()
def update_and_get_user_progress():
	'''
		Return setup progress action states (called via `update_and_get_user_progress` hook)
	'''
	states = {}
	for fn in frappe.get_hooks('update_and_get_user_progress'):
		states.update(frappe.get_attr(fn)())

	return states
