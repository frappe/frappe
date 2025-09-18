# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os

import frappe
from frappe import _
from frappe.build import scrub_html_template
from frappe.model.meta import Meta
from frappe.model.utils import render_include
from frappe.modules import get_module_path, load_doctype_module, scrub
from frappe.utils import get_bench_path, get_html_format
from frappe.utils.data import get_link_to_form

ASSET_KEYS = (
	"__js",
	"__css",
	"__list_js",
	"__calendar_js",
	"__print_formats",
	"__workflow_docs",
	"__form_grid_templates",
	"__listview_template",
	"__tree_js",
	"__dashboard",
	"__kanban_column_fields",
	"__templates",
	"__custom_js",
	"__custom_list_js",
	"__workspaces",
)


def get_meta(doctype, cached=True) -> "FormMeta":
	# don't cache for developer mode as js files, templates may be edited
	cached = cached and not frappe.conf.developer_mode
	key = f"doctype_form_meta::{doctype}"
	if cached:
		meta = frappe.client_cache.get_value(key)
		if not meta:
			# Cache miss - explicitly get meta from DB to avoid mismatches
			meta = FormMeta(doctype, cached=False)
			frappe.client_cache.set_value(key, meta)
	else:
		# NOTE: In developer mode use cached `Meta` for better DX
		#       In prod don't use cached meta when explicitly requesting from DB.
		meta = FormMeta(doctype, cached=frappe.conf.developer_mode)

	return meta


class FormMeta(Meta):
	def __init__(self, doctype, *, cached=True):
		self.__dict__.update(frappe.get_meta(doctype, cached=cached).__dict__)
		self.load_assets()

	def load_assets(self):
		if self.get("__assets_loaded", False):
			return

		if not self.istable:
			self.add_code()
			self.add_custom_script()
			self.load_print_formats()
			self.load_workflows()
			self.load_templates()
			self.load_dashboard()
			self.load_kanban_meta()
			self.load_workspaces()

		self.set("__assets_loaded", True)

	def as_dict(self, no_nulls=False):
		d = super().as_dict(no_nulls=no_nulls)
		__dict = self.__dict__

		for k in ASSET_KEYS:
			d[k] = __dict.get(k)

		return d

	def add_code(self):
		if self.custom:
			return

		path = os.path.join(get_module_path(self.module), "doctype", scrub(self.name))

		def _get_path(fname):
			return os.path.join(path, scrub(fname))

		system_country = frappe.get_system_settings("country")

		self._add_code(_get_path(self.name + ".js"), "__js")
		if system_country:
			self._add_code(_get_path(os.path.join("regional", system_country + ".js")), "__js")

		self._add_code(_get_path(self.name + ".css"), "__css")
		self._add_code(_get_path(self.name + "_list.js"), "__list_js")
		if system_country:
			self._add_code(_get_path(os.path.join("regional", system_country + "_list.js")), "__list_js")

		self._add_code(_get_path(self.name + "_calendar.js"), "__calendar_js")
		self._add_code(_get_path(self.name + "_tree.js"), "__tree_js")

		listview_template = _get_path(self.name + "_list.html")
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
			bench_path = get_bench_path() + "/"
			asset_path = path.replace(bench_path, "")
			comment = f"\n\n/* Adding {asset_path} */\n\n"
			sourceURL = f"\n\n//# sourceURL={scrub(self.name) + fieldname}"
			self.set(fieldname, (self.get(fieldname) or "") + comment + js + sourceURL)

	def add_html_templates(self, path):
		if self.custom:
			return
		templates = dict()
		for fname in os.listdir(path):
			if fname.endswith(".html"):
				with open(os.path.join(path, fname), encoding="utf-8") as f:
					templates[fname.split(".", 1)[0]] = scrub_html_template(f.read())

		self.set("__templates", templates or None)

	def add_code_via_hook(self, hook, fieldname):
		for path in get_code_files_via_hooks(hook, self.name):
			self._add_code(path, fieldname)

	def add_custom_script(self):
		"""embed all require files"""
		# custom script
		client_scripts = (
			frappe.get_all(
				"Client Script",
				filters={"dt": self.name, "enabled": 1},
				fields=["name", "script", "view"],
				order_by="creation asc",
			)
			or ""
		)

		list_script = ""
		form_script = ""
		for script in client_scripts:
			if not script.script:
				continue

			if script.view == "List":
				list_script += f"""
// {script.name}
{script.script}

"""

			elif script.view == "Form":
				form_script += f"""
// {script.name}
{script.script}

"""

		file = scrub(self.name)
		form_script += f"\n\n//# sourceURL={file}__custom_js"
		list_script += f"\n\n//# sourceURL={file}__custom_list_js"

		self.set("__custom_js", form_script)
		self.set("__custom_list_js", list_script)

	def _show_missing_doctype_msg(self, df):
		# A link field is referring to non-existing doctype, this usually happens when
		# customizations are removed or some custom app is removed but hasn't cleaned
		# up after itself.
		frappe.clear_last_message()

		msg = _("Field {0} is referring to non-existing doctype {1}.").format(
			frappe.bold(df.fieldname), frappe.bold(df.options)
		)

		if df.get("is_custom_field"):
			custom_field_link = get_link_to_form("Custom Field", df.name)
			msg += " " + _("Please delete the field from {0} or add the required doctype.").format(
				custom_field_link
			)

		frappe.throw(msg, title=_("Missing DocType"))

	def load_print_formats(self):
		print_formats = frappe.db.sql(
			"""select * FROM `tabPrint Format`
			WHERE doc_type=%s AND docstatus<2 and disabled=0""",
			(self.name,),
			as_dict=1,
			update={"doctype": "Print Format"},
		)

		self.set("__print_formats", print_formats)

	def load_workflows(self):
		# get active workflow
		workflow_name = self.get_workflow()
		workflow_docs = []

		if workflow_name and frappe.db.exists("Workflow", workflow_name):
			workflow = frappe.get_doc("Workflow", workflow_name)
			workflow_docs.append(workflow)

			workflow_docs.extend(frappe.get_doc("Workflow State", d.state) for d in workflow.get("states"))
		self.set("__workflow_docs", workflow_docs)

	def load_templates(self):
		if not self.custom:
			module = load_doctype_module(self.name)
			app = module.__name__.split(".", 1)[0]
			templates = {}
			if hasattr(module, "form_grid_templates"):
				for key, path in module.form_grid_templates.items():
					templates[key] = get_html_format(frappe.get_app_path(app, path))

				self.set("__form_grid_templates", templates)

	def load_dashboard(self):
		self.set("__dashboard", self.get_dashboard_data())

	def load_workspaces(self):
		Shortcut = frappe.qb.DocType("Workspace Shortcut")
		Workspace = frappe.qb.DocType("Workspace")
		shortcut = (
			frappe.qb.from_(Shortcut)
			.select(Shortcut.parent)
			.inner_join(Workspace)
			.on(Workspace.name == Shortcut.parent)
			.where(Shortcut.link_to == self.name)
			.where(Shortcut.type == "DocType")
			.where(Workspace.public == 1)
			.run()
		)
		if shortcut:
			self.set("__workspaces", [shortcut[0][0]])
		else:
			Link = frappe.qb.DocType("Workspace Link")
			link = (
				frappe.qb.from_(Link)
				.select(Link.parent)
				.inner_join(Workspace)
				.on(Workspace.name == Link.parent)
				.where(Link.link_type == "DocType")
				.where(Link.link_to == self.name)
				.where(Workspace.public == 1)
				.run()
			)

			if link:
				self.set("__workspaces", [link[0][0]])

	def load_kanban_meta(self):
		self.load_kanban_column_fields()

	def load_kanban_column_fields(self):
		try:
			values = frappe.get_list(
				"Kanban Board", fields=["field_name"], filters={"reference_doctype": self.name}
			)

			fields = [x["field_name"] for x in values]
			fields = list(set(fields))
			self.set("__kanban_column_fields", fields)
		except frappe.PermissionError:
			# no access to kanban board
			pass


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
