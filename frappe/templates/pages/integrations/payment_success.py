# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals

import frappe
no_cache = True

def get_context(context):
	token = frappe.local.form_dict.token
