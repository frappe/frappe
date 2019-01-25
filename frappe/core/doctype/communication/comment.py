# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, absolute_import
import frappe
from frappe import _
import json
from frappe.core.doctype.user.user import extract_mentions
from frappe.utils import get_fullname, get_link_to_form
from frappe.website.render import clear_cache
from frappe.database.schema import add_column
from frappe.exceptions import ImplicitCommitError

def on_trash(doc):
	if doc.communication_type != "Comment":
		return

	if doc.reference_doctype == "Message":
		return

	if (doc.comment_type or "Comment") != "Comment":
		frappe.only_for("System Manager")

	_comments = get_comments_from_parent(doc)
	for c in _comments:
		if c.get("name")==doc.name:
			_comments.remove(c)

	update_comments_in_parent(doc.reference_doctype, doc.reference_name, _comments)

def update_comment_in_doc(doc):
	"""Updates `_comments` (JSON) property in parent Document.
	Creates a column `_comments` if property does not exist.

	Only user created comments Communication or Comment of type Comment are saved.

	`_comments` format

		{
			"comment": [String],
			"by": [user],
			"name": [Comment Document name]
		}"""

	if doc.communication_type not in ("Comment", "Communication"):
		return

	if doc.communication_type == 'Comment' and doc.comment_type != 'Comment':
		# other updates
		return

	def get_content(doc):
		return (doc.content[:97] + '...') if len(doc.content) > 100 else doc.content

	if doc.reference_doctype and doc.reference_name and doc.content:
		_comments = get_comments_from_parent(doc)

		updated = False
		for c in _comments:
			if c.get("name")==doc.name:
				c["comment"] = get_content(doc)
				updated = True

		if not updated:
			_comments.append({
				"comment": get_content(doc),
				"by": doc.sender or doc.owner,
				"name": doc.name
			})

		update_comments_in_parent(doc.reference_doctype, doc.reference_name, _comments)

def notify_mentions(doc):
	if doc.communication_type != "Comment":
		return

	if doc.reference_doctype and doc.reference_name and doc.content and doc.comment_type=="Comment":
		mentions = extract_mentions(doc.content)

		if not mentions:
			return

		sender_fullname = get_fullname(frappe.session.user)
		title_field = frappe.get_meta(doc.reference_doctype).get_title_field()
		title = doc.reference_name if title_field == "name" else \
			frappe.db.get_value(doc.reference_doctype, doc.reference_name, title_field)

		if title != doc.reference_name:
			parent_doc_label = "{0}: {1} (#{2})".format(_(doc.reference_doctype),
				title, doc.reference_name)
		else:
			parent_doc_label = "{0}: {1}".format(_(doc.reference_doctype),
				doc.reference_name)

		subject = _("{0} mentioned you in a comment in {1}").format(sender_fullname, parent_doc_label)

		recipients = [frappe.db.get_value("User", {"enabled": 1, "name": name, "user_type": "System User", "allowed_in_mentions": 1}, "email")
			for name in mentions]
		link = get_link_to_form(doc.reference_doctype, doc.reference_name, label=parent_doc_label)

		frappe.sendmail(
			recipients=recipients,
			sender=frappe.session.user,
			subject=subject,
			template="mentioned_in_comment",
			args={
				"body_content": _("{0} mentioned you in a comment in {1}").format(sender_fullname, link),
				"comment": doc,
				"link": link
			},
			header=[_('New Mention'), 'orange']
		)

def get_comments_from_parent(doc):
	try:
		_comments = frappe.db.get_value(doc.reference_doctype, doc.reference_name, "_comments") or "[]"

	except Exception as e:
		if frappe.db.is_missing_table_or_column(e):
			_comments = "[]"

		else:
			raise

	try:
		return json.loads(_comments)
	except ValueError:
		return []

def update_comments_in_parent(reference_doctype, reference_name, _comments):
	"""Updates `_comments` property in parent Document with given dict.

	:param _comments: Dict of comments."""
	if not reference_doctype or frappe.db.get_value("DocType", reference_doctype, "issingle"):
		return

	try:
		# use sql, so that we do not mess with the timestamp
		frappe.db.sql("""update `tab%s` set `_comments`=%s where name=%s""" % (reference_doctype,
			"%s", "%s"), (json.dumps(_comments), reference_name))

	except Exception as e:
		if frappe.db.is_column_missing(e) and getattr(frappe.local, 'request', None):
			# missing column and in request, add column and update after commit
			frappe.local._comments = (getattr(frappe.local, "_comments", [])
				+ [(reference_doctype, reference_name, _comments)])
		else:
			raise ImplicitCommitError

	else:
		if not frappe.flags.in_patch:
			reference_doc = frappe.get_doc(reference_doctype, reference_name)
			if getattr(reference_doc, "route", None):
				clear_cache(reference_doc.route)

def add_info_comment(**kwargs):
	kwargs.update({
		"doctype": "Communication",
		"communication_type": "Comment",
		"comment_type": "Info",
		"status": "Closed"
	})
	return frappe.get_doc(kwargs).insert(ignore_permissions=True)

def update_comments_in_parent_after_request():
	"""update _comments in parent if _comments column is missing"""
	if hasattr(frappe.local, "_comments"):
		for (reference_doctype, reference_name, _comments) in frappe.local._comments:
			add_column(reference_doctype, "_comments", "Text")
			update_comments_in_parent(reference_doctype, reference_name, _comments)

		frappe.db.commit()
