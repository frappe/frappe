# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.utils.caching import site_cache


def get_jenv():
	import frappe
	from frappe.utils.safe_exec import get_safe_globals

	if jenv := getattr(frappe.local, "jenv", None):
		return jenv

	default_jenv = _get_jenv()
	jenv = default_jenv.overlay()
	# XXX: This is safe to share between requests, the only reason why we are overlaying jenv is to
	# reuse cache but still have request specific jenv object.
	if not frappe._dev_server:
		jenv.cache = default_jenv.cache

	# Note: Overlay by default is "linked", we need to copy everything we are updating.
	jenv.globals = default_jenv.globals.copy()
	jenv.filters = default_jenv.filters.copy()

	jenv.globals.update(get_safe_globals())
	methods, filters = get_jinja_hooks()
	jenv.globals.update(methods or {})
	jenv.filters.update(filters or {})

	frappe.local.jenv = jenv

	return jenv


@site_cache(ttl=10 * 60, maxsize=4)
def _get_jenv():
	# XXX: DO NOT use any thread/request specific data in this function!
	# Some functionality like `get_safe_globals` appears safe but internally uses request local
	# data.

	from jinja2 import DebugUndefined
	from jinja2.sandbox import SandboxedEnvironment

	from frappe.utils.safe_exec import UNSAFE_ATTRIBUTES

	UNSAFE_ATTRIBUTES = UNSAFE_ATTRIBUTES - {"format", "format_map"}

	class FrappeSandboxedEnvironment(SandboxedEnvironment):
		def is_safe_attribute(self, obj, attr, *args, **kwargs):
			if attr in UNSAFE_ATTRIBUTES:
				return False

			return super().is_safe_attribute(obj, attr, *args, **kwargs)

	# frappe will be loaded last, so app templates will get precedence
	jenv = FrappeSandboxedEnvironment(loader=get_jloader(), undefined=DebugUndefined, cache_size=32)
	set_filters(jenv)

	return jenv


def get_template(path):
	jenv = get_jenv()
	# Note: jenv globals are reapplied here because we don't have true "global"/"local" separation.
	# Ideally globals should never change as per Jinja design.
	return jenv.get_template(path, globals=jenv.globals)


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


def render_template(template, context=None, is_path=None, safe_render=True):
	"""Render a template using Jinja

	:param template: path or HTML containing the jinja template
	:param context: dict of properties to pass to the template
	:param is_path: (optional) assert that the `template` parameter is a path
	:param safe_render: (optional) prevent server side scripting via jinja templating
	"""
	if not template:
		return ""

	from jinja2 import TemplateError
	from jinja2.sandbox import SandboxedEnvironment

	from frappe import _, get_traceback, throw

	if context is None:
		context = {}

	try:
		if is_path or guess_is_path(template):
			is_path = True
			compiled_template = get_template(template)
		else:
			jenv: SandboxedEnvironment = get_jenv()
			if safe_render and ".__" in template:
				throw(_("Illegal template"))

			compiled_template = jenv.from_string(template)
	except TemplateError:
		import html

		throw(
			title="Jinja Template Error",
			msg=f"<pre>{template}</pre><pre>{html.escape(get_traceback())}</pre>",
		)

	import time

	from frappe.utils.logger import get_logger

	logger = get_logger("render-template")
	try:
		start_time = time.monotonic()
		return compiled_template.render(context)
	except Exception as e:
		import html

		throw(title="Context Error", msg=f"<pre>{html.escape(get_traceback())}</pre>", exc=e)
	finally:
		if is_path:
			logger.debug(f"Rendering time: {time.monotonic() - start_time:.6f} seconds ({template})")
		else:
			logger.debug(f"Rendering time: {time.monotonic() - start_time:.6f} seconds")


def guess_is_path(template):
	# template can be passed as a path or content
	# if its single line and ends with a html, then its probably a path
	if "\n" not in template and "." in template:
		extn = template.rsplit(".")[-1]
		if extn in ("html", "css", "scss", "py", "md", "json", "js", "xml", "txt"):
			return True

	return False


def get_jloader():
	jloader = _get_jloader()
	frappe.local.jloader = jloader  # backward compat
	return jloader


@site_cache(ttl=10 * 60, maxsize=8)
def _get_jloader():
	from jinja2 import ChoiceLoader, PackageLoader, PrefixLoader

	import frappe

	apps = frappe.get_hooks("template_apps")
	if not apps:
		apps = list(reversed(frappe.get_installed_apps(_ensure_on_bench=True)))

	if "frappe" not in apps:
		apps.append("frappe")

	jloader = ChoiceLoader(
		# search for something like app/templates/...
		[PrefixLoader({app: PackageLoader(app, ".") for app in apps})]
		# search for something like templates/...
		+ [PackageLoader(app, ".") for app in apps]
	)

	return jloader


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
