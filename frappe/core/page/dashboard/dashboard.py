# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals
import frappe


@frappe.whitelist()
def get_data(dashboard_name):
    results = frappe.get_attr(dashboard_name)()
    return results
