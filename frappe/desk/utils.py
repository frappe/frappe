# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe

def get_doctype_route(name):
	return name.lower().replace(' ', '-')