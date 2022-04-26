# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE
"""
	frappe.coverage
	~~~~~~~~~~~~~~~~

	Coverage settings for frappe
"""

STANDARD_INCLUSIONS = ["*.py"]

STANDARD_EXCLUSIONS = [
	"*.js",
	"*.xml",
	"*.pyc",
	"*.css",
	"*.less",
	"*.scss",
	"*.vue",
	"*.html",
	"*/test_*",
	"*/node_modules/*",
	"*/doctype/*/*_dashboard.py",
	"*/patches/*",
]

FRAPPE_EXCLUSIONS = [
	"*/tests/*",
	"*/commands/*",
	"*/frappe/change_log/*",
	"*/frappe/exceptions*",
	"*frappe/setup.py",
	"*/doctype/*/*_dashboard.py",
	"*/patches/*",
]
