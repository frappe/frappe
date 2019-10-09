# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# metadata

from __future__ import unicode_literals
import frappe, os
from frappe.model.meta import Meta
from frappe.modules import scrub, get_module_path, load_doctype_module
from frappe.utils import get_html_format
from frappe.translate import make_dict_from_messages, extract_messages_from_code
from frappe.model.utils import render_include
from frappe.build import scrub_html_template

import io

from six import iteritems

def get_meta(doctype, cached=True):
	# don't cache for developer mode as js files, templates may be edited
	if cached and not frappe.conf.developer_mode:
		meta = frappe.cache().hget("form_meta", doctype)
		if meta:
			meta = FormMeta(meta)
		else:
			meta = FormMeta(doctype)
			frappe.cache().hset("form_meta", doctype, meta.as_dict())
	else:
		meta = FormMeta(doctype)

	if frappe.local.lang != 'en':
		meta.set_translations(frappe.local.lang)

	return meta

class FormMeta(Meta):
	def __init__(self, doctype):
		super(FormMeta, self).__init__(doctype)
		self.load_assets()

	def load_assets(self):
		if self.get('__assets_loaded', False):
			return

		self.add_search_fields()
		self.add_linked_document_type()

		if not self.istable:
			self.add_code()
			self.add_custom_script()
			self.load_print_formats()
			self.load_workflows()
			self.load_templates()
			self.load_dashboard()
			self.load_kanban_meta()

		self.set('__assets_loaded', True)

	def as_dict(self, no_nulls=False):
		d = super(FormMeta, self).as_dict(no_nulls=no_nulls)

		for k in ("__js", "__css", "__list_js", "__calendar_js", "__map_js",
			"__linked_with", "__messages", "__print_formats", "__workflow_docs",
			"__form_grid_templates", "__listview_template", "__tree_js",
			"__dashboard", "__kanban_column_fields", '__templates',
			'__custom_js'):
			d[k] = self.get(k)

		# d['fields'] = d.get('fields', [])

		for i, df in enumerate(d.get("fields") or []):
			for k in ("search_fields", "is_custom_field", "linked_document_type"):
				df[k] = self.get("fields")[i].get(k)

		return d

	def add_code(self):
		if self.custom:
			return

		path = os.path.join(get_module_path(self.module), 'doctype', scrub(self.name))
		def _get_path(fname):
			return os.path.join(path, scrub(fname))

		system_country = frappe.get_system_settings("country")

		self._add_code(_get_path(self.name + '.js'), '__js')
		if system_country:
			self._add_code(_get_path(os.path.join('regional', system_country + '.js')), '__js')

		self._add_code(_get_path(self.name + '.css'), "__css")
		self._add_code(_get_path(self.name + '_list.js'), '__list_js')
		if system_country:
			self._add_code(_get_path(os.path.join('regional', system_country + '_list.js')), '__list_js')

		self._add_code(_get_path(self.name + '_calendar.js'), '__calendar_js')
		self._add_code(_get_path(self.name + '_tree.js'), '__tree_js')

		listview_template = _get_path(self.name + '_list.html')
		if os.path.exists(listview_template):
			self.set("__listview_template", get_html_format(listview_template))

		self.add_code_via_hook("doctype_js", "__js")
		self.add_code_via_hook("doctype_list_js", "__list_js")
		self.add_code_via_hook("doctype_tree_js", "__tree_js")
		self.add_code_via_hook("doctype_calendar_js", "__calendar_js")
		self.add_html_templates(path)

	def _add_code(self, path, fieldname):
		js = get_js(path)
		if js:
			self.set(fieldname, (self.get(fieldname) or "")
				+ "\n\n/* Adding {0} */\n\n".format(path) + js)

	def add_html_templates(self, path):
		if self.custom:
			return
		templates = dict()
		for fname in os.listdir(path):
			if fname.endswith(".html"):
				with io.open(os.path.join(path, fname), 'r', encoding = 'utf-8') as f:
					templates[fname.split('.')[0]] = scrub_html_template(f.read())

		self.set("__templates", templates or None)

	def add_code_via_hook(self, hook, fieldname):
		for path in get_code_files_via_hooks(hook, self.name):
			self._add_code(path, fieldname)

	def add_custom_script(self):
		"""embed all require files"""
		# custom script
		custom = frappe.db.get_value("Custom Script", {"dt": self.name}, "script") or ""

		self.set("__custom_js", custom)

	def add_search_fields(self):
		"""add search fields found in the doctypes indicated by link fields' options"""
		for df in self.get("fields", {"fieldtype": "Link", "options":["!=", "[Select]"]}):
			if df.options:
				search_fields = frappe.get_meta(df.options).search_fields
				if search_fields:
					search_fields = search_fields.split(",")
					df.search_fields = [sf.strip() for sf in search_fields]

	def add_linked_document_type(self):
		for df in self.get("fields", {"fieldtype": "Link"}):
			if df.options:
				try:
					df.linked_document_type = frappe.get_meta(df.options).document_type
				except frappe.DoesNotExistError:
					# edge case where options="[Select]"
					pass

	def load_print_formats(self):
		print_formats = frappe.db.sql("""select * FROM `tabPrint Format`
			WHERE doc_type=%s AND docstatus<2 and disabled=0""", (self.name,), as_dict=1,
			update={"doctype":"Print Format"})

		self.set("__print_formats", print_formats, as_value=True)

	def load_workflows(self):
		# get active workflow
		workflow_name = self.get_workflow()
		workflow_docs = []

		if workflow_name and frappe.db.exists("Workflow", workflow_name):
			workflow = frappe.get_doc("Workflow", workflow_name)
			workflow_docs.append(workflow)

			for d in workflow.get("states"):
				workflow_docs.append(frappe.get_doc("Workflow State", d.state))

		self.set("__workflow_docs", workflow_docs, as_value=True)


	def load_templates(self):
		if not self.custom:
			module = load_doctype_module(self.name)
			app = module.__name__.split(".")[0]
			templates = {}
			if hasattr(module, "form_grid_templates"):
				for key, path in iteritems(module.form_grid_templates):
					templates[key] = get_html_format(frappe.get_app_path(app, path))

				self.set("__form_grid_templates", templates)

	def set_translations(self, lang):
		self.set("__messages", frappe.get_lang_dict("doctype", self.name))

		# set translations for grid templates
		if self.get("__form_grid_templates"):
			for content in self.get("__form_grid_templates").values():
				messages = extract_messages_from_code(content)
				messages = make_dict_from_messages(messages)
				self.get("__messages").update(messages, as_value=True)

	def load_dashboard(self):
		if self.custom:
			return
		self.set('__dashboard', self.get_dashboard_data())

	def load_kanban_meta(self):
		self.load_kanban_column_fields()

	def load_kanban_column_fields(self):
		values = frappe.get_list(
			'Kanban Board', fields=['field_name'],
			filters={'reference_doctype': self.name})

		fields = [x['field_name'] for x in values]
		fields = list(set(fields))
		self.set("__kanban_column_fields", fields, as_value=True)

def get_code_files_via_hooks(hook, name):
	code_files = []
	for app_name in frappe.get_installed_apps():
		code_hook = frappe.get_hooks(hook, default={}, app_name=app_name)
		if not code_hook:
			continue

		files = code_hook.get(name, [])
		if not isinstance(files, list):
			files = [files]

		for file in files:
			path = frappe.get_app_path(app_name, *file.strip("/").split("/"))
			code_files.append(path)

	return code_files

def get_js(path):
	js = frappe.read_file(path)
	if js:
		return render_include(js)
