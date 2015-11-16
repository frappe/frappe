# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: See license.txt

from __future__ import unicode_literals

import frappe, json, os
from frappe.utils import strip
from frappe.translate import (set_default_language, get_dict,
	get_lang_dict, send_translations, get_language_from_code)

@frappe.whitelist()
def setup_complete(args):
	"""Calls hooks for `setup_wizard_complete`, sets home page as `desktop`
	and clears cache. If wizard breaks, calls `setup_wizard_exception` hook"""
	args = process_args(args)

	try:
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
