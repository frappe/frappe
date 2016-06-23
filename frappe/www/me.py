# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils.user import get_fullname_and_avatar
import frappe.www.list

no_cache = 1
no_sitemap = 1

def get_context(context):
	context.show_sidebar=True