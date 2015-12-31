# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: See license.txt

from __future__ import unicode_literals

import frappe, json, os
from frappe.utils import strip
from frappe.translate import (set_default_language, get_dict,
	get_lang_dict, send_translations, get_language_from_code)
from frappe.geo.country_info import get_country_info

@frappe.whitelist()
def setup_complete(args):
	"""Calls hooks for `setup_wizard_complete`, sets home page as `desktop`
	and clears cache. If wizard breaks, calls `setup_wizard_exception` hook"""
	args = process_args(args)

	try:
		if args.language and args.language != "english":
			set_default_language(args.language)

		frappe.clear_cache()

		# update system settings
		update_system_settings(args)

		for method in frappe.get_hooks("setup_wizard_complete"):
			frappe.get_attr(method)(args)

		frappe.db.set_default('desktop:home_page', 'desktop')
		frappe.db.commit()
		frappe.clear_cache()
	except:
		if args:
			traceback = frappe.get_traceback()
			for hook in frappe.get_hooks("setup_wizard_exception"):
				frappe.get_attr(hook)(traceback, args)

		raise

	else:
		for hook in frappe.get_hooks("setup_wizard_success"):
			frappe.get_attr(hook)(args)

def update_system_settings(args):
	number_format = get_country_info(args.get("country")).get("number_format", "#,###.##")

	# replace these as float number formats, as they have 0 precision
	# and are currency number formats and not for floats
	if number_format=="#.###":
		number_format = "#.###,##"
	elif number_format=="#,###":
		number_format = "#,###.##"

	system_settings = frappe.get_doc("System Settings", "System Settings")
	system_settings.update({
		"language": args.get("language"),
		"time_zone": args.get("timezone"),
		"float_precision": 3,
		'date_format': frappe.db.get_value("Country", args.get("country"), "date_format"),
		'number_format': number_format,
		'enable_scheduler': 1 if not frappe.flags.in_test else 0
	})
	system_settings.save()

def process_args(args):
	if not args:
		args = frappe.local.form_dict
	if isinstance(args, basestring):
		args = json.loads(args)

	args = frappe._dict(args)

	# strip the whitespace
	for key, value in args.items():
		if isinstance(value, basestring):
			args[key] = strip(value)

	return args

@frappe.whitelist()
def load_messages(language):
	"""Load translation messages for given langauge from all `setup_wizard_requires`
	javascript files"""
	frappe.clear_cache()
	set_default_language(language)
	m = get_dict("page", "setup-wizard")

	for path in frappe.get_hooks("setup_wizard_requires"):
		# common folder `assets` served from `sites/`
		js_file_path = os.path.abspath(frappe.get_site_path("..", *path.strip("/").split("/")))
		m.update(get_dict("jsfile", js_file_path))

	m.update(get_dict("boot"))
	send_translations(m)
	return frappe.local.lang

@frappe.whitelist()
def load_languages():
	return {
		"default_language": get_language_from_code(frappe.local.lang),
		"languages": sorted(get_lang_dict().keys())
	}
