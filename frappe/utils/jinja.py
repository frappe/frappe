# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

def get_jenv():
	import frappe

	if not getattr(frappe.local, 'jenv', None):
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

def get_email_from_template(name, args):
	from jinja2 import TemplateNotFound

	args = args or {}
	try:
		message = get_template('templates/emails/' + name + '.html').render(args)
	except TemplateNotFound as e:
		raise e

	try:
		text_content = get_template('templates/emails/' + name + '.txt').render(args)
	except TemplateNotFound:
		text_content = None

	return (message, text_content)

def validate_template(html):
	"""Throws exception if there is a syntax error in the Jinja Template"""
	import frappe
	from jinja2 import TemplateSyntaxError

	jenv = get_jenv()
	try:
		jenv.from_string(html)
	except TemplateSyntaxError as e:
		frappe.msgprint('Line {}: {}'.format(e.lineno, e.message))
		frappe.throw(frappe._("Syntax error in template"))

def render_template(template, context, is_path=None, safe_render=True):
	'''Render a template using Jinja

	:param template: path or HTML containing the jinja template
	:param context: dict of properties to pass to the template
	:param is_path: (optional) assert that the `template` parameter is a path
	:param safe_render: (optional) prevent server side scripting via jinja templating 
	'''

	from frappe import throw

	if not template:
		return ""

	# if it ends with .html then its a freaking path, not html
	if (is_path
		or template.startswith("templates/")
		or (template.endswith('.html') and '\n' not in template)):
		return get_jenv().get_template(template).render(context)
	else:
		if safe_render and ".__" in template:
			throw("Illegal template")
		return get_jenv().from_string(template).render(context)

def get_allowed_functions_for_jenv():
	import os, json
	import frappe
	import frappe.utils
	import frappe.utils.data
	from frappe.utils.autodoc import automodule, get_version
	from frappe.model.document import get_controller
	from frappe.website.utils import (get_shade, get_toc, get_next_link)
	from frappe.modules import scrub
	import mimetypes
	from html2text import html2text
	from frappe.www.printview import get_visible_columns

	datautils = {}
	if frappe.db:
		date_format = frappe.db.get_default("date_format") or "yyyy-mm-dd"
	else:
		date_format = 'yyyy-mm-dd'

	for key, obj in frappe.utils.data.__dict__.items():
		if key.startswith("_"):
			# ignore
			continue

		if hasattr(obj, "__call__"):
			# only allow functions
			datautils[key] = obj

	if "_" in getattr(frappe.local, 'form_dict', {}):
		del frappe.local.form_dict["_"]

	user = getattr(frappe.local, "session", None) and frappe.local.session.user or "Guest"

	out = {
		# make available limited methods of frappe
		"frappe": {
			"_": frappe._,
			"get_url": frappe.utils.get_url,
			'format': frappe.format_value,
			"format_value": frappe.format_value,
			'date_format': date_format,
			"format_date": frappe.utils.data.global_date_format,
			"form_dict": getattr(frappe.local, 'form_dict', {}),
			"local": frappe.local,
			"get_hooks": frappe.get_hooks,
			"get_meta": frappe.get_meta,
			"get_doc": frappe.get_doc,
			"get_cached_doc": frappe.get_cached_doc,
			"get_list": frappe.get_list,
			"get_all": frappe.get_all,
			'get_system_settings': frappe.get_system_settings,
			"utils": datautils,
			"user": user,
			"get_fullname": frappe.utils.get_fullname,
			"get_gravatar": frappe.utils.get_gravatar_url,
			"full_name": frappe.local.session.data.full_name if getattr(frappe.local, "session", None) else "Guest",
			"render_template": frappe.render_template,
			'session': {
				'user': user,
				'csrf_token': frappe.local.session.data.csrf_token if getattr(frappe.local, "session", None) else ''
			},
		},
		'style': {
			'border_color': '#d1d8dd'
		},
		"autodoc": {
			"get_version": get_version,
			"automodule": automodule,
			"get_controller": get_controller
		},
		'get_toc': get_toc,
		'get_next_link': get_next_link,
		"_": frappe._,
		"get_shade": get_shade,
		"scrub": scrub,
		"guess_mimetype": mimetypes.guess_type,
		'html2text': html2text,
		'json': json,
		"dev_server": 1 if os.environ.get('DEV_SERVER', False) else 0
	}

	if not frappe.flags.in_setup_help:
		out['get_visible_columns'] = get_visible_columns
		out['frappe']['date_format'] = date_format
		out['frappe']["db"] = {
			"get_value": frappe.db.get_value,
			"get_default": frappe.db.get_default,
			"escape": frappe.db.escape,
		}

	# load jenv methods from hooks.py
	for method_name, method_definition in get_jenv_customization("methods"):
		out[method_name] = frappe.get_attr(method_definition)

	return out

def get_jloader():
	import frappe
	if not getattr(frappe.local, 'jloader', None):
		from jinja2 import ChoiceLoader, PackageLoader, PrefixLoader

		if frappe.local.flags.in_setup_help:
			apps = ['frappe']
		else:
			apps = frappe.get_hooks('template_apps')
			if not apps:
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

	if frappe.flags.in_setup_help: return

	# load jenv_filters from hooks.py
	for filter_name, filter_function in get_jenv_customization("filters"):
		jenv.filters[filter_name] = frappe.get_attr(filter_function)

def get_jenv_customization(customizable_type):
	import frappe

	if getattr(frappe.local, "site", None):
		for app in frappe.get_installed_apps():
			for jenv_customizable, jenv_customizable_definition in frappe.get_hooks(app_name=app).get("jenv", {}).items():
				if customizable_type == jenv_customizable:
					for data in jenv_customizable_definition:
						split_data = data.split(":")
						yield split_data[0], split_data[1]
