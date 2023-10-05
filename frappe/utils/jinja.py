# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
def get_jenv():
	"""
	Get the Jinja2 environment.

	This function checks if the Jinja2 environment has already been created and stored
	in the 'frappe.local' object. If not, it creates a new environment using
	the 'FrappeSandboxedEnvironment' class, sets the loader and undefined
	attributes, updates the globals and filters with safe methods and filters,
	and stores the environment in 'frappe.local.jenv'.

	Returns:
	    Jinja2.Environment: The Jinja2 environment.
	"""
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
	"""
	Get the Jinja2 template specified by the given path.

	This function calls the 'get_jenv' function to obtain the Jinja2 environment
	and retrieves the template specified by the given path.

	Args:
	    path (str): The path of the template.

	Returns:
	    Jinja2.Template: The Jinja2 template.
	"""
	return get_jenv().get_template(path)


def get_email_from_template(name, args):
	"""Render an email template with the given name and arguments.

	This function uses the Jinja2 library to render an HTML template and a
	corresponding text template.

	Args:
	    name (str): The name of the template.
	    args (dict): A dictionary of arguments to be passed to the template.

	Returns:
	    tuple: A tuple containing the rendered message and text content.
	"""
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
	"""Validate the syntax of a Jinja template.

	This function checks for any syntax errors in the given HTML template using the
	Jinja2 library.

	Args:
	    html (str): The HTML template to validate.

	Raises:
	    TemplateSyntaxError: If a syntax error is found in the template.
	"""
	from jinja2 import TemplateSyntaxError

	import frappe

	if not html:
	    return
	jenv = get_jenv()
	try:
	    jenv.from_string(html)
	except TemplateSyntaxError as e:
	    frappe.msgprint(f"Line {e.lineno}: {e.message}")
	    frappe.throw(frappe._("Syntax error in template"))


def render_template(template, context=None, is_path=None, safe_render=True):
	"""
	Render a template using Jinja

	Args:
	    template (str): path or HTML containing the jinja template context
	    (dict, optional): dict of properties to pass to the template is_path
	    (bool, optional): assert that the `template` parameter is a path
	    safe_render (bool, optional): prevent server side scripting via jinja
	        templating

	Returns:
	    str: rendered template
	"""

	from jinja2 import TemplateError

	from frappe import _, get_traceback, throw

	if not template:
	    return ""

	if context is None:
	    context = {}

	if is_path or guess_is_path(template):
	    return get_jenv().get_template(template).render(context)
	else:
	    if safe_render and ".__" in template:
	        throw(_("Illegal template"))
	    try:
	        return get_jenv().from_string(template).render(context)
	    except TemplateError:
	        throw(
	        	title="Jinja Template Error",
	        	msg=f"<pre>{template}</pre><pre>{get_traceback()}</pre>",
	        )


def guess_is_path(template):
	"""
	Guess whether the template is a path or content based on its format.

	Args:
	    template (str): the template to guess

	Returns:
	    bool: True if the template is a path, False otherwise
	"""
	# template can be passed as a path or content
	# if its single line and ends with a html, then its probably a path
	if "\n" not in template and "." in template:
	    extn = template.rsplit(".")[-1]
	    if extn in ("html", "css", "scss", "py", "md", "json", "js", "xml"):
	        return True

	return False


def get_jloader():
	"""
	Get the Jinja2 loader for the current Frappe instance.

	This function returns an instance of the Jinja2 ChoiceLoader class,
	which contains PrefixLoader instances and PackageLoader instances for each
	template app in the Frappe instance.

	Returns:
	    jinja2.ChoiceLoader: The Jinja2 loader for the current Frappe instance.
	"""
	import frappe

	if not getattr(frappe.local, "jloader", None):
	    from jinja2 import ChoiceLoader, PackageLoader, PrefixLoader

	    apps = frappe.get_hooks("template_apps")
	    if not apps:
	        apps = list(
	        	reversed(frappe.local.flags.web_pages_apps or frappe.get_installed_apps(_ensure_on_bench=True))
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
	"""
	Set the filters for the Jinja2 environment.

	This function updates the filters dictionary in the
	Jinja2 environment with the 'json', 'len', 'int', 'str',
	and 'flt' filters.

	Args:
	    jenv (jinja2.Environment): The Jinja2 environment.
	"""
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
	"""
	Returns a tuple of (methods, filters) each containing a dict of method name and
	method definition pair.
	"""
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
