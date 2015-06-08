# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# metadata

from __future__ import unicode_literals
import frappe, os
from frappe.model.meta import Meta
from frappe.modules import scrub, get_module_path, load_doctype_module
from frappe.model.workflow import get_workflow_name
from frappe.utils import get_html_format
from frappe.translate import make_dict_from_messages, extract_messages_from_code
from frappe.utils.jinja import render_include
from frappe.build import html_to_js_template

######

def get_meta(doctype, cached=True):
	if cached and not frappe.conf.developer_mode:
		meta = frappe.cache().hget("form_meta", doctype, lambda: FormMeta(doctype))
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
		self.add_search_fields()

		if not self.istable:
			self.add_linked_with()
			self.add_code()
			self.load_print_formats()
			self.load_workflows()
			self.load_templates()

	def as_dict(self, no_nulls=False):
		d = super(FormMeta, self).as_dict(no_nulls=no_nulls)
		for k in ("__js", "__css", "__list_js", "__calendar_js", "__map_js",
			"__linked_with", "__messages", "__print_formats", "__workflow_docs",
			"__form_grid_templates", "__listview_template"):
			d[k] = self.get(k)

		for i, df in enumerate(d.get("fields")):
			for k in ("link_doctype", "search_fields", "is_custom_field"):
				df[k] = self.get("fields")[i].get(k)

		return d

	def add_code(self):
		path = os.path.join(get_module_path(self.module), 'doctype', scrub(self.name))
		def _get_path(fname):
			return os.path.join(path, scrub(fname))

		self._add_code(_get_path(self.name + '.js'), '__js')
		self._add_code(_get_path(self.name + '.css'), "__css")
		self._add_code(_get_path(self.name + '_list.js'), '__list_js')
		self._add_code(_get_path(self.name + '_calendar.js'), '__calendar_js')

		listview_template = _get_path(self.name + '_list.html')
		if os.path.exists(listview_template):
			self.set("__listview_template", get_html_format(listview_template))

		self.add_code_via_hook("doctype_js", "__js")
		self.add_code_via_hook("doctype_list_js", "__list_js")
		self.add_custom_script()
		self.add_html_templates(path)

	def _add_code(self, path, fieldname):
		js = frappe.read_file(path)
		if js:
			self.set(fieldname, (self.get(fieldname) or "") + "\n\n" + render_include(js))

	def add_html_templates(self, path):
		if self.custom:
			return
		js = ""
		for fname in os.listdir(path):
			if fname.endswith(".html"):
				with open(os.path.join(path, fname), 'r') as f:
					template = unicode(f.read(), "utf-8")
					js += html_to_js_template(fname, template)

		self.set("__js", (self.get("__js") or "") + js)

	def add_code_via_hook(self, hook, fieldname):
		for app_name in frappe.get_installed_apps():
			code_hook = frappe.get_hooks(hook, default={}, app_name=app_name)
			if not code_hook:
				continue

			files = code_hook.get(self.name, [])
			if not isinstance(files, list):
				files = [files]

			for file in files:
				path = frappe.get_app_path(app_name, *file.strip("/").split("/"))
				self._add_code(path, fieldname)

	def add_custom_script(self):
		"""embed all require files"""
		# custom script
		custom = frappe.db.get_value("Custom Script", {"dt": self.name,
			"script_type": "Client"}, "script") or ""

		self.set("__js", (self.get('__js') or '') + "\n\n" + custom)

	def add_search_fields(self):
		"""add search fields found in the doctypes indicated by link fields' options"""
		for df in self.get("fields", {"fieldtype": "Link", "options":["!=", "[Select]"]}):
			if df.options:
				search_fields = frappe.get_meta(df.options).search_fields
				if search_fields:
					df.search_fields = map(lambda sf: sf.strip(), search_fields.split(","))

	def add_linked_with(self):
		"""add list of doctypes this doctype is 'linked' with"""
		links = frappe.db.sql("""select parent, fieldname from tabDocField
			where (fieldtype="Link" and options=%s)
			or (fieldtype="Select" and options=%s)""", (self.name, "link:"+ self.name))
		links += frappe.db.sql("""select dt as parent, fieldname from `tabCustom Field`
			where (fieldtype="Link" and options=%s)
			or (fieldtype="Select" and options=%s)""", (self.name, "link:"+ self.name))

		links = dict(links)

		ret = {}

		for dt in links:
			ret[dt] = { "fieldname": links[dt] }

		if links:
			for grand_parent, options in frappe.db.sql("""select parent, options from tabDocField
				where fieldtype="Table"
					and options in (select name from tabDocType
						where istable=1 and name in (%s))""" % ", ".join(["%s"] * len(links)) ,tuple(links)):

				ret[grand_parent] = {"child_doctype": options, "fieldname": links[options] }
				if options in ret:
					del ret[options]

		links = frappe.db.sql("""select dt from `tabCustom Field`
			where (fieldtype="Table" and options=%s)""", (self.name))
		links += frappe.db.sql("""select parent from tabDocField
			where (fieldtype="Table" and options=%s)""", (self.name))

		for dt, in links:
			if not dt in ret:
				ret[dt] = {"get_parent": True}

		self.set("__linked_with", ret, as_value=True)

	def load_print_formats(self):
		print_formats = frappe.db.sql("""select * FROM `tabPrint Format`
			WHERE doc_type=%s AND docstatus<2 and ifnull(disabled, 0)=0""", (self.name,), as_dict=1,
			update={"doctype":"Print Format"})

		self.set("__print_formats", print_formats, as_value=True)

	def load_workflows(self):
		# get active workflow
		workflow_name = get_workflow_name(self.name)
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
				for key, path in module.form_grid_templates.iteritems():
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


