# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

def get_jenv():
	import frappe

	if not frappe.local.jenv:
		from jinja2 import Environment, DebugUndefined

		# frappe will be loaded last, so app templates will get precedence
		jenv = Environment(loader = get_jloader(),
			undefined=DebugUndefined)
		set_filters(jenv)

		jenv.globals.update(get_allowed_functions_for_jenv())

		frappe.local.jenv = jenv

	return frappe.local.jenv

def get_template(path):
	return get_jenv().get_template(path)

def render_template(template, context):
	return get_jenv().from_string(template).render(context)

def get_allowed_functions_for_jenv():
	import frappe
	import frappe.utils
	import frappe.utils.data
	from frappe.utils.autodoc import automodule, get_doclink, get_version
	from frappe.model.document import get_controller

	datautils = {}
	for key, obj in frappe.utils.data.__dict__.items():
		if key.startswith("_"):
			# ignore
			continue

		if hasattr(obj, "__call__"):
			# only allow functions
			datautils[key] = obj

	if "_" in frappe.local.form_dict:
		del frappe.local.form_dict["_"]

	return {
		# make available limited methods of frappe
		"frappe": {
			"_": frappe._,
			"get_url": frappe.utils.get_url,
			"format_value": frappe.format_value,
			"format_date": frappe.utils.data.global_date_format,
			"form_dict": frappe.local.form_dict,
			"local": frappe.local,
			"get_hooks": frappe.get_hooks,
			"get_meta": frappe.get_meta,
			"get_doc": frappe.get_doc,
			"db": {
				"get_value": frappe.db.get_value,
			},
			"get_list": frappe.get_list,
			"get_all": frappe.get_all,
			"utils": datautils,
			"user": hasattr(frappe.local, "session") and frappe.local.session.user or "Guest",
			"date_format": frappe.db.get_default("date_format") or "yyyy-mm-dd",
			"get_fullname": frappe.utils.get_fullname,
			"get_gravatar": frappe.utils.get_gravatar,
			"full_name": hasattr(frappe.local, "session") and frappe.local.session.data.full_name or "Guest"
		},
		"autodoc": {
			"get_version": get_version,
			"get_doclink": get_doclink,
			"automodule": automodule,
			"get_controller": get_controller
		},
		"get_visible_columns": \
			frappe.get_attr("frappe.templates.pages.print.get_visible_columns"),
		"_": frappe._
	}

def get_jloader():
	import frappe
	if not frappe.local.jloader:
		from jinja2 import ChoiceLoader, PackageLoader

		apps = frappe.get_installed_apps()
		apps.remove("frappe")

		frappe.local.jloader = ChoiceLoader([PackageLoader(app, ".") \
				for app in apps + ["frappe"]])

	return frappe.local.jloader

def set_filters(jenv):
	import frappe
	from frappe.utils import global_date_format, cint, cstr, flt
	from frappe.website.utils import get_hex_shade
	from markdown2 import markdown
	from json import dumps

	jenv.filters["global_date_format"] = global_date_format
	jenv.filters["markdown"] = markdown
	jenv.filters["json"] = dumps
	jenv.filters["get_hex_shade"] = get_hex_shade
	jenv.filters["len"] = len
	jenv.filters["int"] = cint
	jenv.filters["str"] = cstr
	jenv.filters["flt"] = flt

	# load jenv_filters from hooks.py
	for app in frappe.get_all_apps(True):
		for jenv_filter in (frappe.get_hooks(app_name=app).jenv_filter or []):
			filter_name, filter_function = jenv_filter.split(":")
			jenv.filters[filter_name] = frappe.get_attr(filter_function)

def render_include(content):
	from frappe.utils import cstr

	content = cstr(content)
	if "{% include" in content:
		content = get_jenv().from_string(content).render()
	return content
