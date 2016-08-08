# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
	Utilities for using modules
"""
import frappe, os
import frappe.utils
from frappe import _

lower_case_files_for = ['DocType', 'Page', 'Report',
	"Workflow", 'Module Def', 'Desktop Item', 'Workflow State', 'Workflow Action', 'Print Format',
	"Website Theme", 'Web Form']

def scrub(txt):
	return frappe.scrub(txt)

def scrub_dt_dn(dt, dn):
	"""Returns in lowercase and code friendly names of doctype and name for certain types"""
	ndt, ndn = dt, dn
	if dt in lower_case_files_for:
		ndt, ndn = scrub(dt), scrub(dn)

	return ndt, ndn

def get_module_path(module):
	"""Returns path of the given module"""
	return frappe.get_module_path(module)

def get_doc_path(module, doctype, name):
	dt, dn = scrub_dt_dn(doctype, name)
	return os.path.join(get_module_path(module), dt, dn)

def reload_doc(module, dt=None, dn=None, force=True):
	from frappe.modules.import_file import import_files
	return import_files(module, dt, dn, force=force)

def export_doc(doctype, name, module=None):
	"""Write a doc to standard path."""
	from frappe.modules.export_file import write_document_file
	print doctype, name

	if not module: module = frappe.db.get_value('DocType', name, 'module')
	write_document_file(frappe.get_doc(doctype, name), module)

def get_doctype_module(doctype):
	"""Returns **Module Def** name of given doctype."""
	def make_modules_dict():
		return dict(frappe.db.sql("select name, module from tabDocType"))
	return frappe.cache().get_value("doctype_modules", make_modules_dict)[doctype]

doctype_python_modules = {}
def load_doctype_module(doctype, module=None, prefix="", suffix=""):
	"""Returns the module object for given doctype."""
	if not module:
		module = get_doctype_module(doctype)

	app = get_module_app(module)

	key = (app, doctype, prefix, suffix)

	if key not in doctype_python_modules:
		doctype_python_modules[key] = frappe.get_module(get_module_name(doctype, module, prefix, suffix))

	return doctype_python_modules[key]

def get_module_name(doctype, module, prefix="", suffix="", app=None):
	return '{app}.{module}.doctype.{doctype}.{prefix}{doctype}{suffix}'.format(\
		app = scrub(app or get_module_app(module)),
		module = scrub(module),
		doctype = scrub(doctype),
		prefix=prefix,
		suffix=suffix)

def get_module_app(module):
	return frappe.local.module_app[scrub(module)]

def get_app_publisher(module):
	app = frappe.local.module_app[scrub(module)]
	if not app:
		frappe.throw(_("App not found"))
	app_publisher = frappe.get_hooks(hook="app_publisher", app_name=app)[0]
	return app_publisher

def make_boilerplate(template, doc, opts=None):
	target_path = get_doc_path(doc.module, doc.doctype, doc.name)
	template_name = template.replace("controller", scrub(doc.name))
	target_file_path = os.path.join(target_path, template_name)

	app_publisher = get_app_publisher(doc.module)

	if not os.path.exists(target_file_path):
		if not opts:
			opts = {}

		with open(target_file_path, 'w') as target:
			with open(os.path.join(get_module_path("core"), "doctype", scrub(doc.doctype),
				"boilerplate", template), 'r') as source:
				target.write(frappe.utils.encode(
					frappe.utils.cstr(source.read()).format(app_publisher=app_publisher,
						classname=doc.name.replace(" ", ""), doctype=doc.name, **opts)
				))
