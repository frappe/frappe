# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
import frappe

@frappe.whitelist()
def get_leaderboard_config():
	leaderboard_config = frappe._dict()
	leaderboard_hooks = frappe.get_hooks('leaderboards')
	for hook in leaderboard_hooks:
		leaderboard_config.update(frappe.get_attr(hook)())

	return leaderboard_config