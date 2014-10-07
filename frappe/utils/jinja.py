# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals
from jinja2 import Template

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
	context.update(get_allowed_functions_for_jenv())
	template = Template(template)
	return template.render(**context)

def get_allowed_functions_for_jenv():
	import frappe
	import frappe.utils.data

	datautils = {}
	for key, obj in frappe.utils.data.__dict__.items():
		if key.startswith("_"):
			# ignore
			continue

		if hasattr(obj, "__call__"):
			# only allow functions
			datautils[key] = obj

	return {
		# make available limited methods of frappe
		"frappe": {
			"_": frappe._,
			"format_value": frappe.format_value,
			"local": frappe.local,
			"get_hooks": frappe.get_hooks,
			"get_meta": frappe.get_meta,
			"get_doc": frappe.get_doc,
			"get_list": frappe.get_list,
			"utils": datautils,
			"user": frappe.session.user,
			"date_format": frappe.db.get_default("date_format") or "yyyy-mm-dd"
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
