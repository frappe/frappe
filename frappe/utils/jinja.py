# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
	from frappe.model.document import DocumentProxy


def process_context(
	context: dict[Any],
	for_code_completion: bool = False,
	document_proxy_class: type["DocumentProxy"] | None = None,
):
	from frappe.model.document import Document, DocumentProxy

	if not document_proxy_class:  # lazy import
		document_proxy_class = DocumentProxy

	if for_code_completion:

		def process_value(key, value, prefix="", depth=0):
			full_key = f"{prefix}.{key}" if prefix else key
			result = [{"value": full_key, "score": 1000, "meta": "ctx"}]
			if depth >= 2:
				return result

			if isinstance(value, Document):  # on entry
				value = document_proxy_class(value.doctype, value.name)
			if isinstance(value, document_proxy_class):
				for field in value._fieldnames:
					result.extend(process_value(field, getattr(value, field), full_key, depth + 1))
			elif isinstance(value, dict):
				for k, v in value.items():
					result.extend(process_value(k, v, full_key, depth + 1))

			return result

		completion_list = []
		for key, value in context.items():
			completion_list.extend(process_value(key, value))
		return completion_list

	else:

		def process_value(value, depth=0):
			if isinstance(value, Document):
				return document_proxy_class(value.doctype, value.name)
			elif isinstance(value, dict) and not depth >= 2:
				return {k: process_value(v, depth + 1) for k, v in value.items()}
			return value

		return {key: process_value(value) for key, value in context.items()}


def get_jenv():
	import frappe

	if not getattr(frappe.local, "jenv", None):
		from jinja2 import DebugUndefined
		from jinja2.sandbox import SandboxedEnvironment

		from frappe.utils.safe_exec import UNSAFE_ATTRIBUTES, get_safe_globals

		UNSAFE_ATTRIBUTES = UNSAFE_ATTRIBUTES - {"format", "format_map"}

		class FrappeSandboxedEnvironment(SandboxedEnvironment):
			def is_safe_attribute(self, obj, attr, *args, **kwargs):
				if attr in UNSAFE_ATTRIBUTES:
					return False

				return super().is_safe_attribute(obj, attr, *args, **kwargs)

		# frappe will be loaded last, so app templates will get precedence
		jenv = FrappeSandboxedEnvironment(loader=get_jloader(), undefined=DebugUndefined)
		set_filters(jenv)

		jenv.globals.update(get_safe_globals())

		methods, filters = get_jinja_hooks()
		jenv.globals.update(methods or {})
		jenv.filters.update(filters or {})

		frappe.local.jenv = jenv

	return frappe.local.jenv


def get_template(path):
	return get_jenv().get_template(path)


def get_email_from_template(name, args):
	from jinja2 import TemplateNotFound

	args = args or {}
	try:
		message = get_template("templates/emails/" + name + ".html").render(args)
	except TemplateNotFound as e:
		raise e

	try:
		text_content = get_template("templates/emails/" + name + ".txt").render(args)
	except TemplateNotFound:
		text_content = None

	return (message, text_content)


def validate_template(html):
	"""Throws exception if there is a syntax error in the Jinja Template"""
	from jinja2 import TemplateSyntaxError

	import frappe

	if not html:
		return
	jenv = get_jenv()
	try:
		jenv.from_string(html)
	except TemplateSyntaxError as e:
		frappe.throw(f"Syntax error in template as line {e.lineno}: {e.message}")


def render_template(
	template,
	context=None,
	is_path=None,
	safe_render=True,
	document_proxy_class: type["DocumentProxy"] | None = None,
):
	"""Render a template using Jinja

	:param template: path or HTML containing the jinja template
	:param context: dict of properties to pass to the template
	:param is_path: (optional) assert that the `template` parameter is a path
	:param safe_render: (optional) prevent server side scripting via jinja templating
	"""

	from jinja2 import TemplateError

	from frappe import _, get_traceback, throw

	if not template:
		return ""

	if context is None:
		context = {}

	processed_context = process_context(context, document_proxy_class=document_proxy_class)

	if is_path or guess_is_path(template):
		return get_jenv().get_template(template).render(processed_context)
	else:
		if safe_render and ".__" in template:
			throw(_("Illegal template"))
		try:
			return get_jenv().from_string(template).render(processed_context)
		except TemplateError:
			throw(
				title="Jinja Template Error",
				msg=f"<pre>{template}</pre><pre>{get_traceback()}</pre>",
			)


def guess_is_path(template):
	# template can be passed as a path or content
	# if its single line and ends with a html, then its probably a path
	if "\n" not in template and "." in template:
		extn = template.rsplit(".")[-1]
		if extn in ("html", "css", "scss", "py", "md", "json", "js", "xml", "txt"):
			return True

	return False


def get_jloader():
	import frappe

	if not getattr(frappe.local, "jloader", None):
		from jinja2 import ChoiceLoader, PackageLoader, PrefixLoader

		apps = frappe.get_hooks("template_apps")
		if not apps:
			apps = list(
				reversed(
					frappe.local.flags.web_pages_apps or frappe.get_installed_apps(_ensure_on_bench=True)
				)
			)

		if "frappe" not in apps:
			apps.append("frappe")

		frappe.local.jloader = ChoiceLoader(
			# search for something like app/templates/...
			[PrefixLoader({app: PackageLoader(app, ".") for app in apps})]
			# search for something like templates/...
			+ [PackageLoader(app, ".") for app in apps]
		)

	return frappe.local.jloader


def set_filters(jenv):
	import frappe
	from frappe.utils import cint, cstr, flt

	jenv.filters.update(
		{
			"json": frappe.as_json,
			"len": len,
			"int": cint,
			"str": cstr,
			"flt": flt,
		}
	)


def get_jinja_hooks():
	"""Return a tuple of (methods, filters) each containing a dict of method name and method definition pair."""
	import frappe

	if not getattr(frappe.local, "site", None):
		return (None, None)

	from inspect import getmembers, isfunction
	from types import FunctionType, ModuleType

	def get_obj_dict_from_paths(object_paths):
		out = {}
		for obj_path in object_paths:
			try:
				obj = frappe.get_module(obj_path)
			except ModuleNotFoundError:
				obj = frappe.get_attr(obj_path)

			if isinstance(obj, ModuleType):
				functions = getmembers(obj, isfunction)
				for function_name, function in functions:
					out[function_name] = function
			elif isinstance(obj, FunctionType):
				function_name = obj.__name__
				out[function_name] = obj
		return out

	values = frappe.get_hooks("jinja")
	methods, filters = values.get("methods", []), values.get("filters", [])

	method_dict = get_obj_dict_from_paths(methods)
	filter_dict = get_obj_dict_from_paths(filters)

	return method_dict, filter_dict
