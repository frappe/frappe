# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
"""
	Utilities for using modules
"""
import frappe, os, json
import frappe.utils
from frappe import _

def export_module_json(doc, is_standard, module):
	"""Make a folder for the given doc and add its json file (make it a standard
		object that will be synced)"""
	if (not frappe.flags.in_import and getattr(frappe.get_conf(),'developer_mode', 0)
		and is_standard):
		from frappe.modules.export_file import export_to_files

		# json
		export_to_files(record_list=[[doc.doctype, doc.name]], record_module=module,
			create_init=is_standard)

		path = os.path.join(frappe.get_module_path(module), scrub(doc.doctype),
			scrub(doc.name), scrub(doc.name))

		return path

def get_doc_module(module, doctype, name):
	"""Get custom module for given document"""
	module_name = "{app}.{module}.{doctype}.{name}.{name}".format(
			app = frappe.local.module_app[scrub(module)],
			doctype = scrub(doctype),
			module = scrub(module),
			name = scrub(name)
	)
	return frappe.get_module(module_name)

@frappe.whitelist()
def export_customizations(module, doctype, sync_on_migrate=0, with_permissions=0):
	"""Export Custom Field and Property Setter for the current document to the app folder.
		This will be synced with bench migrate"""
	if not frappe.get_conf().developer_mode:
		raise Exception('Not developer mode')

	custom = {'custom_fields': [], 'property_setters': [], 'custom_perms': [],
		'doctype': doctype, 'sync_on_migrate': 1}

	def add(_doctype):
		custom['custom_fields'] += frappe.get_all('Custom Field',
			fields='*', filters={'dt': _doctype})
		custom['property_setters'] += frappe.get_all('Property Setter',
			fields='*', filters={'doc_type': _doctype})

	add(doctype)

	if with_permissions:
		custom['custom_perms'] = frappe.get_all('Custom DocPerm',
			fields='*', filters={'parent': doctype})

	# also update the custom fields and property setters for all child tables
	for d in frappe.get_meta(doctype).get_table_fields():
		export_customizations(module, d.options, sync_on_migrate, with_permissions)

	if custom["custom_fields"] or custom["property_setters"] or custom["custom_perms"]:
		folder_path = os.path.join(get_module_path(module), 'custom')
		if not os.path.exists(folder_path):
			os.makedirs(folder_path)

		path = os.path.join(folder_path, scrub(doctype)+ '.json')
		with open(path, 'w') as f:
			f.write(frappe.as_json(custom))

		frappe.msgprint(_('Customizations for <b>{0}</b> exported to:<br>{1}').format(doctype,path))

def sync_customizations(app=None):
	'''Sync custom fields and property setters from custom folder in each app module'''

	if app:
		apps = [app]
	else:
		apps = frappe.get_installed_apps()

	for app_name in apps:
		for module_name in frappe.local.app_modules.get(app_name) or []:
			folder = frappe.get_app_path(app_name, module_name, 'custom')

			if os.path.exists(folder):
				for fname in os.listdir(folder):
					with open(os.path.join(folder, fname), 'r') as f:
						data = json.loads(f.read())

					if data.get('sync_on_migrate'):
						sync_customizations_for_doctype(data, folder)


def sync_customizations_for_doctype(data, folder):
	'''Sync doctype customzations for a particular data set'''
	from frappe.core.doctype.doctype.doctype import validate_fields_for_doctype

	doctype = data['doctype']
	update_schema = False

	def sync(key, custom_doctype, doctype_fieldname):
		doctypes = list(set(map(lambda row: row.get(doctype_fieldname), data[key])))

		# sync single doctype exculding the child doctype
		def sync_single_doctype(doc_type):
			frappe.db.sql('delete from `tab{0}` where `{1}` =%s'.format(
				custom_doctype, doctype_fieldname), doc_type)
			for d in data[key]:
				if d.get(doctype_fieldname) == doc_type:
					d['doctype'] = custom_doctype
					doc = frappe.get_doc(d)
					doc.db_insert()

		for doc_type in doctypes:
			# only sync the parent doctype and child doctype if there isn't any other child table json file
			if doc_type == doctype or not os.path.exists(os.path.join(folder, frappe.scrub(doc_type)+".json")):
				sync_single_doctype(doc_type)

	if data['custom_fields']:
		sync('custom_fields', 'Custom Field', 'dt')
		update_schema = True

	if data['property_setters']:
		sync('property_setters', 'Property Setter', 'doc_type')

	if data.get('custom_perms'):
		sync('custom_perms', 'Custom DocPerm', 'parent')

	print('Updating customizations for {0}'.format(doctype))
	validate_fields_for_doctype(doctype)

	if update_schema and not frappe.db.get_value('DocType', doctype, 'issingle'):
		frappe.db.updatedb(doctype)

def scrub(txt):
	return frappe.scrub(txt)

def scrub_dt_dn(dt, dn):
	"""Returns in lowercase and code friendly names of doctype and name for certain types"""
	return scrub(dt), scrub(dn)

def get_module_path(module):
	"""Returns path of the given module"""
	return frappe.get_module_path(module)

def get_doc_path(module, doctype, name):
	dt, dn = scrub_dt_dn(doctype, name)
	return os.path.join(get_module_path(module), dt, dn)

def reload_doc(module, dt=None, dn=None, force=False, reset_permissions=False):
	from frappe.modules.import_file import import_files
	return import_files(module, dt, dn, force=force, reset_permissions=reset_permissions)

def export_doc(doctype, name, module=None):
	"""Write a doc to standard path."""
	from frappe.modules.export_file import write_document_file
	print(doctype, name)

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

	module_name = get_module_name(doctype, module, prefix, suffix)

	try:
		if key not in doctype_python_modules:
			doctype_python_modules[key] = frappe.get_module(module_name)
	except ImportError as e:
		raise ImportError('Module import failed for {0} ({1})'.format(doctype, module_name + ' Error: ' + str(e)))

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
	if template_name.endswith('._py'):
		template_name = template_name[:-4] + '.py'
	target_file_path = os.path.join(target_path, template_name)

	if not doc: doc = {}

	app_publisher = get_app_publisher(doc.module)

	if not os.path.exists(target_file_path):
		if not opts:
			opts = {}

		with open(target_file_path, 'w') as target:
			with open(os.path.join(get_module_path("core"), "doctype", scrub(doc.doctype),
				"boilerplate", template), 'r') as source:
				target.write(frappe.as_unicode(
					frappe.utils.cstr(source.read()).format(
						app_publisher=app_publisher,
						year=frappe.utils.nowdate()[:4],
						classname=doc.name.replace(" ", ""),
						doctype=doc.name, **opts)
				))
