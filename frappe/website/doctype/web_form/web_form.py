# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json
import os

import frappe
from frappe import _, scrub
from frappe.core.api.file import get_max_file_size
from frappe.core.doctype.file import remove_file_by_url
from frappe.desk.form.meta import get_code_files_via_hooks
from frappe.modules.utils import export_module_json, get_doc_module
from frappe.rate_limiter import rate_limit
from frappe.utils import dict_with_keys, strip_html
from frappe.website.utils import get_boot_data, get_comment_list, get_sidebar_items
from frappe.website.website_generator import WebsiteGenerator


class WebForm(WebsiteGenerator):
	website = frappe._dict(no_cache=1)

	def onload(self):
		super().onload()

	def validate(self):
		super().validate()

		if not self.module:
			self.module = frappe.db.get_value("DocType", self.doc_type, "module")

		in_user_env = not (
			frappe.flags.in_install
			or frappe.flags.in_patch
			or frappe.flags.in_test
			or frappe.flags.in_fixtures
		)
		if in_user_env and self.is_standard and not frappe.conf.developer_mode:
			# only published can be changed for standard web forms
			if self.has_value_changed("published"):
				published_value = self.published
				self.reload()
				self.published = published_value
			else:
				frappe.throw(_("You need to be in developer mode to edit a Standard Web Form"))

		if not frappe.flags.in_import:
			self.validate_fields()

	def validate_fields(self):
		"""Validate all fields are present"""
		from frappe.model import no_value_fields

		missing = []
		meta = frappe.get_meta(self.doc_type)
		for df in self.web_form_fields:
			if df.fieldname and (df.fieldtype not in no_value_fields and not meta.has_field(df.fieldname)):
				missing.append(df.fieldname)

		if missing:
			frappe.throw(_("Following fields are missing:") + "<br>" + "<br>".join(missing))

	def reset_field_parent(self):
		"""Convert link fields to select with names as options"""
		for df in self.web_form_fields:
			df.parent = self.doc_type

	# export
	def on_update(self):
		"""
		Writes the .txt for this page and if write_content is checked,
		it will write out a .html file
		"""
		path = export_module_json(self, self.is_standard, self.module)

		if path:
			# js
			if not os.path.exists(path + ".js"):
				with open(path + ".js", "w") as f:
					f.write(
						"""frappe.ready(function() {
	// bind events here
})"""
					)

			# py
			if not os.path.exists(path + ".py"):
				with open(path + ".py", "w") as f:
					f.write(
						"""import frappe

def get_context(context):
	# do your magic here
	pass
"""
					)

	def get_context(self, context):
		"""Build context to render the `web_form.html` template"""
		context.in_edit_mode = False
		context.in_view_mode = False

		if frappe.form_dict.is_list:
			context.template = "website/doctype/web_form/templates/web_list.html"
		else:
			context.template = "website/doctype/web_form/templates/web_form.html"

		# check permissions
		if frappe.form_dict.name:
			if frappe.session.user == "Guest":
				frappe.throw(
					_("You need to be logged in to access this {0}.").format(self.doc_type),
					frappe.PermissionError,
				)

			if not frappe.db.exists(self.doc_type, frappe.form_dict.name):
				raise frappe.PageDoesNotExistError()

			if not self.has_web_form_permission(self.doc_type, frappe.form_dict.name):
				frappe.throw(
					_("You don't have the permissions to access this document"), frappe.PermissionError
				)

		if frappe.local.path == self.route:
			path = f"/{self.route}/list" if self.show_list else f"/{self.route}/new"
			frappe.redirect(path)

		if frappe.form_dict.is_list and not self.show_list:
			frappe.redirect(f"/{self.route}/new")

		if frappe.form_dict.is_edit and not self.allow_edit:
			context.in_view_mode = True
			frappe.redirect(f"/{self.route}/{frappe.form_dict.name}")

		if frappe.form_dict.is_edit:
			context.in_edit_mode = True

		if frappe.form_dict.is_read:
			context.in_view_mode = True

		if (
			not frappe.form_dict.is_edit
			and not frappe.form_dict.is_read
			and self.allow_edit
			and frappe.form_dict.name
		):
			context.in_edit_mode = True
			frappe.redirect(f"/{frappe.local.path}/edit")

		if (
			frappe.session.user != "Guest"
			and self.login_required
			and not self.allow_multiple
			and not frappe.form_dict.name
			and not frappe.form_dict.is_list
		):
			condition_json = json.loads(self.condition_json) if self.condition_json else []
			condition_json.append(["owner", "=", frappe.session.user])
			names = frappe.get_all(self.doc_type, filters=condition_json, pluck="name")
			if names:
				context.in_view_mode = True
				frappe.redirect(f"/{self.route}/{names[0]}")

		# Show new form when
		# - User is Guest
		# - Login not required
		route_to_new = frappe.session.user == "Guest" or not self.login_required
		if not frappe.form_dict.is_new and route_to_new:
			frappe.redirect(f"/{self.route}/new")

		self.reset_field_parent()

		# add keys from form_dict to context
		context.update(dict_with_keys(frappe.form_dict, ["is_list", "is_new", "is_edit", "is_read"]))

		for df in self.web_form_fields:
			if df.fieldtype == "Column Break":
				context.has_column_break = True
				break

		# load web form doc
		context.web_form_doc = self.as_dict(no_nulls=True)
		context.web_form_doc.update(
			dict_with_keys(context, ["is_list", "is_new", "in_edit_mode", "in_view_mode"])
		)

		if self.show_sidebar and self.website_sidebar:
			context.sidebar_items = get_sidebar_items(self.website_sidebar)

		if frappe.form_dict.is_list:
			self.load_list_data(context)
		else:
			self.load_form_data(context)

		self.add_custom_context_and_script(context)
		self.load_translations(context)
		self.add_metatags(context)

		context.boot = get_boot_data()
		context.boot["link_title_doctypes"] = frappe.boot.get_link_title_doctypes()

		context.webform_banner_image = self.banner_image
		context.pop("banner_image", None)

	def add_metatags(self, context):
		description = self.meta_description

		if not description and self.introduction_text:
			description = self.introduction_text[:140]

		context.metatags = {
			"name": self.meta_title or self.title,
			"description": description,
			"image": self.meta_image,
		}

	def load_translations(self, context):
		translated_messages = frappe.translate.get_dict("doctype", self.doc_type)
		# Sr is not added by default, had to be added manually
		translated_messages["Sr"] = _("Sr")
		context.translated_messages = frappe.as_json(translated_messages)

	def load_list_data(self, context):
		if not self.list_columns:
			self.list_columns = get_in_list_view_fields(self.doc_type)
			context.web_form_doc.list_columns = self.list_columns

	def load_form_data(self, context):
		"""Load document `doc` and `layout` properties for template"""
		context.parents = []
		if self.show_list:
			context.parents.append(
				{
					"label": _(self.title),
					"route": f"{self.route}/list",
				}
			)

		context.parents = self.get_parents(context)

		if self.breadcrumbs:
			context.parents = frappe.safe_eval(self.breadcrumbs, {"_": _})

		if self.show_list and frappe.form_dict.is_new:
			context.title = _("New {0}").format(context.title)

		context.has_header = (frappe.form_dict.name or frappe.form_dict.is_new) and (
			frappe.session.user != "Guest" or not self.login_required
		)

		if context.success_message:
			context.success_message = frappe.db.escape(context.success_message.replace("\n", "<br>")).strip(
				"'"
			)

		if not context.max_attachment_size:
			context.max_attachment_size = get_max_file_size() / 1024 / 1024

		# For Table fields, server-side processing for meta
		for field in context.web_form_doc.web_form_fields:
			if field.fieldtype == "Table":
				field.fields = get_in_list_view_fields(field.options)

			if field.fieldtype == "Link":
				field.fieldtype = "Autocomplete"
				field.options = get_link_options(
					self.name, field.options, field.allow_read_on_all_link_options
				)

		context.reference_doc = {}

		# load reference doc
		if frappe.form_dict.name:
			context.doc_name = frappe.form_dict.name
			context.reference_doc = frappe.get_doc(self.doc_type, context.doc_name)
			context.web_form_title = context.title
			context.title = (
				strip_html(context.reference_doc.get(context.reference_doc.meta.get_title_field()))
				or context.doc_name
			)
			context.reference_doc.add_seen()
			context.reference_doctype = context.reference_doc.doctype
			context.reference_name = context.reference_doc.name

			if self.show_attachments:
				context.attachments = frappe.get_all(
					"File",
					filters={
						"attached_to_name": context.reference_name,
						"attached_to_doctype": context.reference_doctype,
						"is_private": 0,
					},
					fields=["file_name", "file_url", "file_size"],
				)

			if self.allow_comments:
				context.comment_list = get_comment_list(
					context.reference_doc.doctype, context.reference_doc.name
				)

			context.reference_doc = context.reference_doc.as_dict(no_nulls=True)

	def add_custom_context_and_script(self, context):
		"""Update context from module if standard and append script"""
		if self.is_standard:
			web_form_module = get_web_form_module(self)
			new_context = web_form_module.get_context(context)

			if new_context:
				context.update(new_context)

			js_path = os.path.join(os.path.dirname(web_form_module.__file__), scrub(self.name) + ".js")
			if os.path.exists(js_path):
				script = frappe.render_template(open(js_path).read(), context)

				for path in get_code_files_via_hooks("webform_include_js", context.doc_type):
					custom_js = frappe.render_template(open(path).read(), context)
					script = "\n\n".join([script, custom_js])

				context.script = script

			css_path = os.path.join(os.path.dirname(web_form_module.__file__), scrub(self.name) + ".css")
			if os.path.exists(css_path):
				style = open(css_path).read()

				for path in get_code_files_via_hooks("webform_include_css", context.doc_type):
					custom_css = open(path).read()
					style = "\n\n".join([style, custom_css])

				context.style = style

	def get_parents(self, context):
		parents = None

		if context.is_list and not context.parents:
			parents = [{"title": _("My Account"), "name": "me"}]
		elif context.parents:
			parents = context.parents

		return parents

	def validate_mandatory(self, doc):
		"""Validate mandatory web form fields"""
		missing = []
		for f in self.web_form_fields:
			if f.reqd and doc.get(f.fieldname) in (None, [], ""):
				missing.append(f)

		if missing:
			frappe.throw(
				_("Mandatory Information missing:")
				+ "<br><br>"
				+ "<br>".join(f"{d.label} ({d.fieldtype})" for d in missing)
			)

	def allow_website_search_indexing(self):
		return False

	def has_web_form_permission(self, doctype, name, ptype="read"):
		if frappe.session.user == "Guest":
			return False

		if self.apply_document_permissions:
			return frappe.get_doc(doctype, name).has_permission(permtype=ptype)

		# owner matches
		elif frappe.db.get_value(doctype, name, "owner") == frappe.session.user:
			return True

		elif frappe.has_website_permission(name, ptype=ptype, doctype=doctype):
			return True

		elif check_webform_perm(doctype, name):
			return True

		else:
			return False


def get_web_form_module(doc):
	if doc.is_standard:
		return get_doc_module(doc.module, doc.doctype, doc.name)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=60)
def accept(web_form, data):
	"""Save the web form"""
	data = frappe._dict(json.loads(data))

	files = []
	files_to_delete = []

	web_form = frappe.get_doc("Web Form", web_form)
	doctype = web_form.doc_type
	user = frappe.session.user

	if web_form.anonymous and frappe.session.user != "Guest":
		frappe.session.user = "Guest"

	if data.name and not web_form.allow_edit:
		frappe.throw(_("You are not allowed to update this Web Form Document"))

	frappe.flags.in_web_form = True
	meta = frappe.get_meta(doctype)

	if data.name:
		# update
		doc = frappe.get_doc(doctype, data.name)
	else:
		# insert
		doc = frappe.new_doc(doctype)

	# set values
	for field in web_form.web_form_fields:
		fieldname = field.fieldname
		df = meta.get_field(fieldname)
		value = data.get(fieldname, "")

		if df and df.fieldtype in ("Attach", "Attach Image"):
			if value and "data:" and "base64" in value:
				files.append((fieldname, value))
				if not doc.name:
					doc.set(fieldname, "")
				continue

			elif not value and doc.get(fieldname):
				files_to_delete.append(doc.get(fieldname))

		doc.set(fieldname, value)

	if doc.name:
		if web_form.has_web_form_permission(doctype, doc.name, "write"):
			doc.save(ignore_permissions=True)
		else:
			# only if permissions are present
			doc.save()

	else:
		# insert
		if web_form.login_required and frappe.session.user == "Guest":
			frappe.throw(_("You must login to submit this form"))

		ignore_mandatory = True if files else False

		doc.insert(ignore_permissions=True, ignore_mandatory=ignore_mandatory)

	# add files
	if files:
		for f in files:
			fieldname, filedata = f

			# remove earlier attached file (if exists)
			if doc.get(fieldname):
				remove_file_by_url(doc.get(fieldname), doctype=doctype, name=doc.name)

			# save new file
			filename, dataurl = filedata.split(",", 1)
			_file = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": filename,
					"attached_to_doctype": doctype,
					"attached_to_name": doc.name,
					"content": dataurl,
					"decode": True,
				}
			)
			_file.save()

			# update values
			doc.set(fieldname, _file.file_url)

		doc.save(ignore_permissions=True)

	if files_to_delete:
		for f in files_to_delete:
			if f:
				remove_file_by_url(f, doctype=doctype, name=doc.name)

	if web_form.anonymous and frappe.session.user == "Guest" and user:
		frappe.session.user = user

	frappe.flags.web_form_doc = doc
	return doc


@frappe.whitelist()
def delete(web_form_name, docname):
	web_form = frappe.get_doc("Web Form", web_form_name)

	owner = frappe.db.get_value(web_form.doc_type, docname, "owner")
	if frappe.session.user == owner and web_form.allow_delete:
		frappe.delete_doc(web_form.doc_type, docname, ignore_permissions=True)
	else:
		raise frappe.PermissionError("Not Allowed")


@frappe.whitelist()
def delete_multiple(web_form_name, docnames):
	web_form = frappe.get_doc("Web Form", web_form_name)

	docnames = json.loads(docnames)

	allowed_docnames = []
	restricted_docnames = []

	for docname in docnames:
		owner = frappe.db.get_value(web_form.doc_type, docname, "owner")
		if frappe.session.user == owner and web_form.allow_delete:
			allowed_docnames.append(docname)
		else:
			restricted_docnames.append(docname)

	for docname in allowed_docnames:
		frappe.delete_doc(web_form.doc_type, docname, ignore_permissions=True)

	if restricted_docnames:
		raise frappe.PermissionError(
			"You do not have permisssion to delete " + ", ".join(restricted_docnames)
		)


def check_webform_perm(doctype, name):
	doc = frappe.get_doc(doctype, name)
	if hasattr(doc, "has_webform_permission"):
		if doc.has_webform_permission():
			return True


@frappe.whitelist(allow_guest=True)
def get_web_form_filters(web_form_name):
	web_form = frappe.get_doc("Web Form", web_form_name)
	return [field for field in web_form.web_form_fields if field.show_in_filter]


@frappe.whitelist(allow_guest=True)
def get_form_data(doctype, docname=None, web_form_name=None):
	web_form = frappe.get_doc("Web Form", web_form_name)

	if web_form.login_required and frappe.session.user == "Guest":
		frappe.throw(_("Not Permitted"), frappe.PermissionError)

	out = frappe._dict()
	out.web_form = web_form

	if frappe.session.user != "Guest" and not docname and not web_form.allow_multiple:
		docname = frappe.db.get_value(doctype, {"owner": frappe.session.user}, "name")

	if docname:
		doc = frappe.get_doc(doctype, docname)
		if web_form.has_web_form_permission(doctype, docname, ptype="read"):
			out.doc = doc
		else:
			frappe.throw(_("Not permitted"), frappe.PermissionError)

	# For Table fields, server-side processing for meta
	for field in out.web_form.web_form_fields:
		if field.fieldtype == "Table":
			field.fields = get_in_list_view_fields(field.options)
			out.update({field.fieldname: field.fields})

		if field.fieldtype == "Link":
			field.fieldtype = "Autocomplete"
			field.options = get_link_options(
				web_form_name, field.options, field.allow_read_on_all_link_options
			)

	return out


@frappe.whitelist()
def get_in_list_view_fields(doctype):
	meta = frappe.get_meta(doctype)
	fields = []

	if meta.title_field:
		fields.append(meta.title_field)
	else:
		fields.append("name")

	if meta.has_field("status"):
		fields.append("status")

	fields += [df.fieldname for df in meta.fields if df.in_list_view and df.fieldname not in fields]

	def get_field_df(fieldname):
		if fieldname == "name":
			return {"label": "Name", "fieldname": "name", "fieldtype": "Data"}
		return meta.get_field(fieldname).as_dict()

	return [get_field_df(f) for f in fields]


@frappe.whitelist(allow_guest=True)
def get_link_options(web_form_name, doctype, allow_read_on_all_link_options=False):
	web_form_doc = frappe.get_doc("Web Form", web_form_name)
	doctype_validated = False
	limited_to_user = False
	if web_form_doc.login_required:
		# check if frappe session user is not guest or admin
		if frappe.session.user != "Guest":
			doctype_validated = True

			if not allow_read_on_all_link_options:
				limited_to_user = True
		else:
			frappe.throw(_("You must be logged in to use this form."), frappe.PermissionError)

	else:
		for field in web_form_doc.web_form_fields:
			if field.options == doctype:
				doctype_validated = True
				break

	if doctype_validated:
		link_options, filters = [], {}

		if limited_to_user:
			filters = {"owner": frappe.session.user}

		fields = ["name as value"]

		meta = frappe.get_meta(doctype)

		if meta.title_field and meta.show_title_field_in_link:
			fields.append(f"{meta.title_field} as label")

		link_options = frappe.get_all(doctype, filters, fields)

		if meta.title_field and meta.show_title_field_in_link:
			return json.dumps(link_options, default=str)
		else:
			return "\n".join([doc.value for doc in link_options])

	else:
		raise frappe.PermissionError(
			_("You don't have permission to access the {0} DocType.").format(doctype)
		)
