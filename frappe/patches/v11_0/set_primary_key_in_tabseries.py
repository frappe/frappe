# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe

def execute():
	frappe.db.sql('ALTER table `tabSeries` add PRIMARY KEY (name)')
