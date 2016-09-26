# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
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

def validate_template(html):
	"""Throws exception if there is a syntax error in the Jinja Template"""
	import frappe
	from jinja2 import TemplateSyntaxError

	jenv = get_jenv()
	try:
		jenv.from_string(html)
	except TemplateSyntaxError, e:
		frappe.msgprint('Line {}: {}'.format(e.lineno, e.message))
		frappe.throw(frappe._("Syntax error in template"))

def render_template(template, context, is_path=None):
	'''Render a template using Jinja

	:param template: path or HTML containing the jinja template
	:param context: dict of properties to pass to the template
	:param is_path: (optional) assert that the `template` parameter is a path'''

	# if it ends with .html then its a freaking path, not html
	if (is_path
		or template.startswith("templates/")
		or (template.endswith('.html') and '\n' not in template)):
		return get_jenv().get_template(template).render(context)
	else:
		return get_jenv().from_string(template).render(context)

def get_allowed_functions_for_jenv():
	import os
	import frappe
	import frappe.utils
	import frappe.utils.data
	from frappe.utils.autodoc import automodule, get_version
	from frappe.model.document import get_controller
	from frappe.website.utils import get_shade
	from frappe.modules import scrub
	import mimetypes

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
				"get_default": frappe.db.get_default,
			},
			"get_list": frappe.get_list,
			"get_all": frappe.get_all,
			"utils": datautils,
			"user": getattr(frappe.local, "session", None) and frappe.local.session.user or "Guest",
			"date_format": frappe.db.get_default("date_format") or "yyyy-mm-dd",
			"get_fullname": frappe.utils.get_fullname,
			"get_gravatar": frappe.utils.get_gravatar_url,
			"full_name": getattr(frappe.local, "session", None) and frappe.local.session.data.full_name or "Guest",
			"render_template": frappe.render_template
		},
		"autodoc": {
			"get_version": get_version,
			"automodule": automodule,
			"get_controller": get_controller
		},
		"get_visible_columns": \
			frappe.get_attr("frappe.www.print.get_visible_columns"),
		"_": frappe._,
		"get_shade": get_shade,
		"scrub": scrub,
		"guess_mimetype": mimetypes.guess_type,
		"dev_server": 1 if os.environ.get('DEV_SERVER', False) else 0
	}

def get_jloader():
	import frappe
	if not frappe.local.jloader:
		from jinja2 import ChoiceLoader, PackageLoader, PrefixLoader

		apps = frappe.local.flags.web_pages_apps or frappe.get_installed_apps(sort=True)
		apps.reverse()

		if not "frappe" in apps:
			apps.append('frappe')

		frappe.local.jloader = ChoiceLoader(
			# search for something like app/templates/...
			[PrefixLoader(dict(
				(app, PackageLoader(app, ".")) for app in apps
			))]

			# search for something like templates/...
			+ [PackageLoader(app, ".") for app in apps]
		)

	return frappe.local.jloader

def set_filters(jenv):
	import frappe
	from frappe.utils import global_date_format, cint, cstr, flt, markdown
	from frappe.website.utils import get_shade, abs_url

	jenv.filters["global_date_format"] = global_date_format
	jenv.filters["markdown"] = markdown
	jenv.filters["json"] = frappe.as_json
	jenv.filters["get_shade"] = get_shade
	jenv.filters["len"] = len
	jenv.filters["int"] = cint
	jenv.filters["str"] = cstr
	jenv.filters["flt"] = flt
	jenv.filters["abs_url"] = abs_url

	# load jenv_filters from hooks.py
	for app in frappe.get_installed_apps():
		for jenv_filter in (frappe.get_hooks(app_name=app).jenv_filter or []):
			filter_name, filter_function = jenv_filter.split(":")
			jenv.filters[filter_name] = frappe.get_attr(filter_function)
