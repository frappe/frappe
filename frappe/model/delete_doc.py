# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
import frappe.model.meta
import frappe.defaults
from frappe.utils.file_manager import remove_all
from frappe import _
from rename_doc import dynamic_link_queries
from frappe.model.naming import revert_series_if_last

def delete_doc(doctype=None, name=None, force=0, ignore_doctypes=None, for_reload=False,
	ignore_permissions=False, flags=None, ignore_on_trash=False):
	"""
		Deletes a doc(dt, dn) and validates if it is not submitted and not linked in a live record
	"""
	if not ignore_doctypes: ignore_doctypes = []

	# get from form
	if not doctype:
		doctype = frappe.form_dict.get('dt')
		name = frappe.form_dict.get('dn')

	names = name
	if isinstance(name, basestring):
		names = [name]

	for name in names or []:

		# already deleted..?
		if not frappe.db.exists(doctype, name):
			return

		# delete attachments
		remove_all(doctype, name)

		doc = None
		if doctype=="DocType":
			if for_reload:

				try:
					doc = frappe.get_doc(doctype, name)
				except frappe.DoesNotExistError:
					pass
				else:
					doc.run_method("before_reload")

			else:
				frappe.db.sql("delete from `tabCustom Field` where dt = %s", name)
				frappe.db.sql("delete from `tabCustom Script` where dt = %s", name)
				frappe.db.sql("delete from `tabProperty Setter` where doc_type = %s", name)
				frappe.db.sql("delete from `tabReport` where ref_doctype=%s", name)

			delete_from_table(doctype, name, ignore_doctypes, None)

		else:
			doc = frappe.get_doc(doctype, name)

			if not for_reload:
				if ignore_permissions:
					if not flags: flags = {}
					flags["ignore_permissions"] = ignore_permissions

				if flags:
					doc.flags.update(flags)

				check_permission_and_not_submitted(doc)

				if not ignore_on_trash:
					doc.run_method("on_trash")

				delete_linked_todos(doc)
				delete_linked_comments(doc)
				delete_linked_communications(doc)
				delete_shared(doc)
				# check if links exist
				if not force:
					check_if_doc_is_linked(doc)
					check_if_doc_is_dynamically_linked(doc)

			update_naming_series(doc)
			delete_from_table(doctype, name, ignore_doctypes, doc)
			doc.run_method("after_delete")

		if doc:
			try:
				doc.notify_update()
				insert_feed(doc)
			except ImportError:
				pass

		# delete user_permissions
		frappe.defaults.clear_default(parenttype="User Permission", key=doctype, value=name)

def update_naming_series(doc):
	if doc.meta.autoname:
		if doc.meta.autoname.startswith("naming_series:") \
			and getattr(doc, "naming_series", None):
			revert_series_if_last(doc.naming_series, doc.name)

		elif doc.meta.autoname.split(":")[0] not in ("Prompt", "field", "hash"):
			revert_series_if_last(doc.meta.autoname, doc.name)

def delete_from_table(doctype, name, ignore_doctypes, doc):
	if doctype!="DocType" and doctype==name:
		frappe.db.sql("delete from `tabSingles` where doctype=%s", name)
	else:
		frappe.db.sql("delete from `tab%s` where name=%s" % (frappe.db.escape(doctype), "%s"), (name,))

	# get child tables
	if doc:
		tables = [d.options for d in doc.meta.get_table_fields()]

	else:
		def get_table_fields(field_doctype):
			return frappe.db.sql_list("""select options from `tab{}` where fieldtype='Table'
				and parent=%s""".format(field_doctype), doctype)

		tables = get_table_fields("DocField")
		if not frappe.flags.in_install=="frappe":
			tables += get_table_fields("Custom Field")

	# delete from child tables
	for t in list(set(tables)):
		if t not in ignore_doctypes:
			frappe.db.sql("delete from `tab%s` where parenttype=%s and parent = %s" % (t, '%s', '%s'), (doctype, name))

def check_permission_and_not_submitted(doc):
	# permission
	if frappe.session.user!="Administrator" and not doc.has_permission("delete"):
		frappe.msgprint(_("User not allowed to delete {0}: {1}").format(doc.doctype, doc.name), raise_exception=True)

	# check if submitted
	if doc.docstatus == 1:
		frappe.msgprint(_("{0} {1}: Submitted Record cannot be deleted.").format(doc.doctype, doc.name),
			raise_exception=True)

def check_if_doc_is_linked(doc, method="Delete"):
	"""
		Raises excption if the given doc(dt, dn) is linked in another record.
	"""
	from frappe.model.rename_doc import get_link_fields
	link_fields = get_link_fields(doc.doctype)
	link_fields = [[lf['parent'], lf['fieldname'], lf['issingle']] for lf in link_fields]

	for link_dt, link_field, issingle in link_fields:
		if not issingle:
			item = frappe.db.get_value(link_dt, {link_field:doc.name},
				["name", "parent", "parenttype", "docstatus"], as_dict=True)

			if item and item.parent != doc.name and ((method=="Delete" and item.docstatus<2) or
					(method=="Cancel" and item.docstatus==1)):
				# raise exception only if
				# linked to an non-cancelled doc when deleting
				# or linked to a submitted doc when cancelling
				frappe.throw(_("Cannot delete or cancel because {0} {1} is linked with {2} {3}").format(doc.doctype,
					doc.name, item.parenttype if item.parent else link_dt, item.parent or item.name),
					frappe.LinkExistsError)

def check_if_doc_is_dynamically_linked(doc, method="Delete"):
	for query in dynamic_link_queries:
		for df in frappe.db.sql(query, as_dict=True):
			if frappe.get_meta(df.parent).issingle:

				# dynamic link in single doc
				refdoc = frappe.db.get_singles_dict(df.parent)
				if (refdoc.get(df.options)==doc.doctype
					and refdoc.get(df.fieldname)==doc.name
					and ((method=="Delete" and refdoc.docstatus < 2)
						or (method=="Cancel" and refdoc.docstatus==1))
					):
					# raise exception only if
					# linked to an non-cancelled doc when deleting
					# or linked to a submitted doc when cancelling
					frappe.throw(_("Cannot delete or cancel because {0} {1} is linked with {2} {3}").format(doc.doctype,
						doc.name, df.parent, ""), frappe.LinkExistsError)
			else:
				# dynamic link in table
				for refdoc in frappe.db.sql("""select name, docstatus from `tab{parent}` where
					{options}=%s and {fieldname}=%s""".format(**df), (doc.doctype, doc.name), as_dict=True):

					if ((method=="Delete" and refdoc.docstatus < 2) or (method=="Cancel" and refdoc.docstatus==1)):
						# raise exception only if
						# linked to an non-cancelled doc when deleting
						# or linked to a submitted doc when cancelling
						frappe.throw(_("Cannot delete or cancel because {0} {1} is linked with {2} {3}")\
							.format(doc.doctype, doc.name, df.parent, refdoc.name), frappe.LinkExistsError)

def delete_linked_todos(doc):
	delete_doc("ToDo", frappe.db.sql_list("""select name from `tabToDo`
		where reference_type=%s and reference_name=%s""", (doc.doctype, doc.name)),
		ignore_permissions=True)

def delete_linked_comments(doc):
	"""Delete comments from the document"""
	delete_doc("Comment", frappe.db.sql_list("""select name from `tabComment`
		where comment_doctype=%s and comment_docname=%s""", (doc.doctype, doc.name)), ignore_on_trash=True,
		ignore_permissions=True)

def delete_linked_communications(doc):
	# make communications orphans
	frappe.db.sql("""update `tabCommunication`
		set reference_doctype=null, reference_name=null
		where reference_doctype=%s and reference_name=%s""", (doc.doctype, doc.name))

def insert_feed(doc):
	from frappe.utils import get_fullname

	if frappe.flags.in_install or frappe.flags.in_import or getattr(doc, "no_feed_on_delete", False):
		return

	frappe.get_doc({
		"doctype": "Feed",
		"feed_type": "Label",
		"doc_type": doc.doctype,
		"doc_name": doc.name,
		"subject": _("Deleted"),
		"full_name": get_fullname(doc.owner)
	}).insert(ignore_permissions=True)

def delete_shared(doc):
	delete_doc("DocShare", frappe.db.sql_list("""select name from `tabDocShare`
		where share_doctype=%s and share_name=%s""", (doc.doctype, doc.name)), ignore_on_trash=True)
