# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import functools


@frappe.whitelist()
def get_google_fonts():
	return _get_google_fonts()


@functools.lru_cache()
def _get_google_fonts():
	file_path = frappe.get_app_path("frappe", "data", "google_fonts.json")
	return frappe.parse_json(frappe.read_file(file_path))
