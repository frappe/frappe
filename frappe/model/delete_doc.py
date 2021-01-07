# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import os
from six import string_types, integer_types
import shutil

import frappe
import frappe.defaults
import frappe.model.meta
from frappe import _
from frappe import get_module_path
from frappe.model.dynamic_links import get_dynamic_link_map
from frappe.core.doctype.file.file import remove_all
from frappe.utils.password import delete_all_passwords_for
from frappe.model.naming import revert_series_if_last
from frappe.utils.global_search import delete_for_document
from frappe.desk.doctype.tag.tag import delete_tags_for_document
from frappe.exceptions import FileNotFoundError

doctypes_to_skip = ("Communication", "ToDo", "DocShare", "Email Unsubscribe", "Activity Log", "File",
	"Version", "Document Follow", "Comment" , "View Log", "Tag Link", "Notification Log", "Email Queue")

def delete_doc(doctype=None, name=None, force=0, ignore_doctypes=None, for_reload=False,
	ignore_permissions=False, flags=None, ignore_on_trash=False, ignore_missing=True):
	"""
		Deletes a doc(dt, dn) and validates if it is not submitted and not linked in a live record
	"""
	if not ignore_doctypes: ignore_doctypes = []

	# get from form
	if not doctype:
		doctype = frappe.form_dict.get('dt')
		name = frappe.form_dict.get('dn')

	names = name
	if isinstance(name, string_types) or isinstance(name, integer_types):
		names = [name]

	for name in names or []:

		# already deleted..?
		if not frappe.db.exists(doctype, name):
			if not ignore_missing:
				raise frappe.DoesNotExistError
			else:
				return False

		# delete passwords
		delete_all_passwords_for(doctype, name)

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
				doc = frappe.get_doc(doctype, name)

				update_flags(doc, flags, ignore_permissions)
				check_permission_and_not_submitted(doc)

				frappe.db.sql("delete from `tabCustom Field` where dt = %s", name)
				frappe.db.sql("delete from `tabCustom Script` where dt = %s", name)
				frappe.db.sql("delete from `tabProperty Setter` where doc_type = %s", name)
				frappe.db.sql("delete from `tabReport` where ref_doctype=%s", name)
				frappe.db.sql("delete from `tabCustom DocPerm` where parent=%s", name)
				frappe.db.sql("delete from `__global_search` where doctype=%s", name)

			delete_from_table(doctype, name, ignore_doctypes, None)

			if frappe.conf.developer_mode and not doc.custom and not (
				for_reload
				or frappe.flags.in_migrate
				or frappe.flags.in_install
				or frappe.flags.in_uninstall
			):
				try:
					delete_controllers(name, doc.module)
				except (FileNotFoundError, OSError, KeyError):
					# in case a doctype doesnt have any controller code  nor any app and module
					pass

		else:
			doc = frappe.get_doc(doctype, name)

			if not for_reload:
				update_flags(doc, flags, ignore_permissions)
				check_permission_and_not_submitted(doc)

				if not ignore_on_trash:
					doc.run_method("on_trash")
					doc.flags.in_delete = True
					doc.run_method('on_change')

				# check if links exist
				if not force:
					check_if_doc_is_linked(doc)
					check_if_doc_is_dynamically_linked(doc)

			update_naming_series(doc)
			delete_from_table(doctype, name, ignore_doctypes, doc)
			doc.run_method("after_delete")

			# delete attachments
			remove_all(doctype, name, from_delete=True)

			if not for_reload:
				# Enqueued at the end, because it gets committed
				# All the linked docs should be checked beforehand
				frappe.enqueue('frappe.model.delete_doc.delete_dynamic_links',
					doctype=doc.doctype, name=doc.name,
					is_async=False if frappe.flags.in_test else True)


		# delete global search entry
		delete_for_document(doc)
		# delete tag link entry
		delete_tags_for_document(doc)

		if doc and not for_reload:
			add_to_deleted_document(doc)
			if not frappe.flags.in_patch:
				try:
					doc.notify_update()
					insert_feed(doc)
				except ImportError:
					pass

			# delete user_permissions
			frappe.defaults.clear_default(parenttype="User Permission", key=doctype, value=name)

def add_to_deleted_document(doc):
	'''Add this document to Deleted Document table. Called after delete'''
	if doc.doctype != 'Deleted Document' and frappe.flags.in_install != 'frappe':
		frappe.get_doc(dict(
			doctype='Deleted Document',
			deleted_doctype=doc.doctype,
			deleted_name=doc.name,
			data=doc.as_json(),
			owner=frappe.session.user
		)).db_insert()

def update_naming_series(doc):
	if doc.meta.autoname:
		if doc.meta.autoname.startswith("naming_series:") \
			and getattr(doc, "naming_series", None):
			revert_series_if_last(doc.naming_series, doc.name)

		elif doc.meta.autoname.split(":")[0] not in ("Prompt", "field", "hash"):
			revert_series_if_last(doc.meta.autoname, doc.name)

def delete_from_table(doctype, name, ignore_doctypes, doc):
	if doctype!="DocType" and doctype==name:
		frappe.db.sql("delete from `tabSingles` where `doctype`=%s", name)
	else:
		frappe.db.sql("delete from `tab{0}` where `name`=%s".format(doctype), name)

	# get child tables
	if doc:
		tables = [d.options for d in doc.meta.get_table_fields()]

	else:
		def get_table_fields(field_doctype):
			if field_doctype == 'Custom Field':
				return []

			return [r[0] for r in frappe.get_all(field_doctype,
				fields='options',
				filters={
					'fieldtype': ['in', frappe.model.table_fields],
					'parent': doctype
				},
				as_list=1
			)]

		tables = get_table_fields("DocField")
		if not frappe.flags.in_install=="frappe":
			tables += get_table_fields("Custom Field")

	# delete from child tables
	for t in list(set(tables)):
		if t not in ignore_doctypes:
			frappe.db.sql("delete from `tab%s` where parenttype=%s and parent = %s" % (t, '%s', '%s'), (doctype, name))

def update_flags(doc, flags=None, ignore_permissions=False):
	if ignore_permissions:
		if not flags: flags = {}
		flags["ignore_permissions"] = ignore_permissions

	if flags:
		doc.flags.update(flags)

def check_permission_and_not_submitted(doc):
	# permission
	if (not doc.flags.ignore_permissions
		and frappe.session.user!="Administrator"
		and (
			not doc.has_permission("delete")
			or (doc.doctype=="DocType" and not doc.custom))):
		frappe.msgprint(_("User not allowed to delete {0}: {1}")
			.format(doc.doctype, doc.name), raise_exception=frappe.PermissionError)

	# check if submitted
	if doc.docstatus == 1:
		frappe.msgprint(_("{0} {1}: Submitted Record cannot be deleted. You must {2} Cancel {3} it first.").format(_(doc.doctype), doc.name, "<a href='https://docs.erpnext.com//docs/user/manual/en/setting-up/articles/delete-submitted-document' target='_blank'>", "</a>"),
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
			for item in frappe.db.get_values(link_dt, {link_field:doc.name},
				["name", "parent", "parenttype", "docstatus"], as_dict=True):
				linked_doctype = item.parenttype if item.parent else link_dt

				ignore_linked_doctypes = doc.get('ignore_linked_doctypes') or []

				if linked_doctype in doctypes_to_skip or (linked_doctype in ignore_linked_doctypes and method == 'Cancel'):
					# don't check for communication and todo!
					continue

				if not item:
					continue
				elif method != "Delete"  and (method != "Cancel" or item.docstatus != 1):
					# don't raise exception if not
					# linked to a non-cancelled doc when deleting or to a submitted doc when cancelling
					continue
				elif link_dt == doc.doctype and (item.parent or item.name) == doc.name:
					# don't raise exception if not
					# linked to same item or doc having same name as the item
					continue
				else:
					reference_docname = item.parent or item.name
					raise_link_exists_exception(doc, linked_doctype, reference_docname)

		else:
			if frappe.db.get_value(link_dt, None, link_field) == doc.name:
				raise_link_exists_exception(doc, link_dt, link_dt)

def check_if_doc_is_dynamically_linked(doc, method="Delete"):
	'''Raise `frappe.LinkExistsError` if the document is dynamically linked'''
	for df in get_dynamic_link_map().get(doc.doctype, []):

		ignore_linked_doctypes = doc.get('ignore_linked_doctypes') or []

		if df.parent in doctypes_to_skip or (df.parent in ignore_linked_doctypes and method == 'Cancel'):
			# don't check for communication and todo!
			continue

		meta = frappe.get_meta(df.parent)
		if meta.issingle:
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
				raise_link_exists_exception(doc, df.parent, df.parent)
		else:
			# dynamic link in table
			df["table"] = ", `parent`, `parenttype`, `idx`" if meta.istable else ""
			for refdoc in frappe.db.sql("""select `name`, `docstatus` {table} from `tab{parent}` where
				{options}=%s and {fieldname}=%s""".format(**df), (doc.doctype, doc.name), as_dict=True):

				if ((method=="Delete" and refdoc.docstatus < 2) or (method=="Cancel" and refdoc.docstatus==1)):
					# raise exception only if
					# linked to an non-cancelled doc when deleting
					# or linked to a submitted doc when cancelling

					reference_doctype = refdoc.parenttype if meta.istable else df.parent
					reference_docname = refdoc.parent if meta.istable else refdoc.name
					at_position = "at Row: {0}".format(refdoc.idx) if meta.istable else ""

					raise_link_exists_exception(doc, reference_doctype, reference_docname, at_position)

def raise_link_exists_exception(doc, reference_doctype, reference_docname, row=''):
	doc_link = '<a href="#Form/{0}/{1}">{1}</a>'.format(doc.doctype, doc.name)
	reference_link = '<a href="#Form/{0}/{1}">{1}</a>'.format(reference_doctype, reference_docname)

	#hack to display Single doctype only once in message
	if reference_doctype == reference_docname:
		reference_doctype = ''

	frappe.throw(_('Cannot delete or cancel because {0} {1} is linked with {2} {3} {4}')
		.format(doc.doctype, doc_link, reference_doctype, reference_link, row), frappe.LinkExistsError)

def delete_dynamic_links(doctype, name):
	delete_references('ToDo', doctype, name, 'reference_type')
	delete_references('Email Unsubscribe', doctype, name)
	delete_references('DocShare', doctype, name, 'share_doctype', 'share_name')
	delete_references('Version', doctype, name, 'ref_doctype', 'docname')
	delete_references('Comment', doctype, name)
	delete_references('View Log', doctype, name)
	delete_references('Document Follow', doctype, name, 'ref_doctype', 'ref_docname')
	delete_references('Notification Log', doctype, name, 'document_type', 'document_name')

	# unlink communications
	clear_timeline_references(doctype, name)
	clear_references('Communication', doctype, name)

	clear_references('Activity Log', doctype, name)
	clear_references('Activity Log', doctype, name, 'timeline_doctype', 'timeline_name')

def delete_references(doctype, reference_doctype, reference_name,
		reference_doctype_field = 'reference_doctype', reference_name_field = 'reference_name'):
	frappe.db.sql('''delete from `tab{0}`
		where {1}=%s and {2}=%s'''.format(doctype, reference_doctype_field, reference_name_field), # nosec
		(reference_doctype, reference_name))

def clear_references(doctype, reference_doctype, reference_name,
		reference_doctype_field = 'reference_doctype', reference_name_field = 'reference_name'):
	frappe.db.sql('''update
			`tab{0}`
		set
			{1}=NULL, {2}=NULL
		where
			{1}=%s and {2}=%s'''.format(doctype, reference_doctype_field, reference_name_field), # nosec
		(reference_doctype, reference_name))

def clear_timeline_references(link_doctype, link_name):
	frappe.db.sql("""DELETE FROM `tabCommunication Link`
		WHERE `tabCommunication Link`.link_doctype=%s AND `tabCommunication Link`.link_name=%s""", (link_doctype, link_name))

def insert_feed(doc):
	if (
		frappe.flags.in_install
		or frappe.flags.in_uninstall
		or frappe.flags.in_import
		or getattr(doc, "no_feed_on_delete", False)
	):
		return

	from frappe.utils import get_fullname

	frappe.get_doc({
		"doctype": "Comment",
		"comment_type": "Deleted",
		"reference_doctype": doc.doctype,
		"subject": "{0} {1}".format(_(doc.doctype), doc.name),
		"full_name": get_fullname(doc.owner),
	}).insert(ignore_permissions=True)


def delete_controllers(doctype, module):
	"""
	Delete controller code in the doctype folder
	"""
	module_path = get_module_path(module)
	dir_path = os.path.join(module_path, 'doctype', frappe.scrub(doctype))

	shutil.rmtree(dir_path)
