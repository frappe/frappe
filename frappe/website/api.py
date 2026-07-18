# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Public website API — the deliberate guest-accessible surface.

Every endpoint here is reachable from the website (most of them by Guest
users), so this module concentrates what used to be scattered across web
form, comments, discussions, contact, help article, page-view tracking,
personal data deletion and email unsubscribe modules into one reviewable
file. Handle with care: changes here are security-sensitive.

The old dotted paths keep working via aliases in the original modules.
"""

import json
from contextlib import suppress
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import frappe
import frappe.utils
from frappe import _
from frappe.public_api import public
from frappe.rate_limiter import rate_limit
from frappe.templates.includes.comments.comments import (
	EMAIL_PATTERN,
	URLS_COMMENT_PATTERN,
)
from frappe.templates.includes.comments.comments import (
	get_limit as get_comment_rate_limit,
)
from frappe.utils import cint, escape_html, now_datetime, validate_email_address
from frappe.utils.caching import redis_cache
from frappe.utils.html_utils import clean_html
from frappe.utils.verified_command import verify_request
from frappe.website.doctype.web_form.web_form import (
	WebForm,
	get_in_list_view_fields,
	get_web_form_list_fields,
	process_link_field,
)
from frappe.website.doctype.web_page_view.web_page_view import is_tracking_enabled
from frappe.website.utils import clear_cache

if TYPE_CHECKING:
	from frappe.model.document import Document
	from frappe.website.doctype.web_form_request.web_form_request import WebFormRequest

# ---------------------------------------------------------------------------
# Web Forms
# ---------------------------------------------------------------------------


@public(group="Website")
@frappe.whitelist(methods=["POST", "PUT"], allow_guest=True)
@rate_limit(key="web_form", limit=10, seconds=60)
def accept_web_form(web_form: str, data: str | dict, web_form_request_key: str | None = None) -> "Document":
	"""Save (insert or update) a document submitted through a web form.

	Permissions follow the web form's own configuration (login_required,
	allow_edit, allow_incomplete, request keys), not Role Permissions.

	:param web_form: name of the Web Form
	:param data: the submitted form values, as JSON or dict
	:param web_form_request_key: key of a Web Form Request granting access
	:return: The saved document.
	"""
	from frappe.core.doctype.file.utils import remove_file_by_url

	data = frappe._dict(frappe.parse_json(data))

	files = []
	files_to_delete = []

	web_form = frappe.get_lazy_doc("Web Form", web_form)
	doctype = web_form.doc_type
	user = frappe.session.user
	web_form_request = web_form.get_web_form_request(
		web_form_request_key,
		docname=data.name,
		for_update=True,
		allow_used=bool(data.name) or bool(web_form.allow_multiple),
	)

	if web_form.login_required and frappe.session.user == "Guest":
		frappe.throw(_("You must login to use this form"))

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

	# Set ignore_mandatory flag if allow_incomplete is enabled
	if web_form.allow_incomplete:
		doc.flags.ignore_mandatory = True

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

	if web_form_request:
		for fieldname, value in web_form_request.get_doc_values().items():
			if meta.has_field(fieldname):
				doc.set(fieldname, value)

	if doc.name:
		if web_form_request:
			# Access was granted by the request key (often as Guest), not by
			# Role Permissions on the target DocType. allow_edit is enforced
			# above when data.name is set.
			doc.save(ignore_permissions=True)
			if not web_form_request.first_used_on:
				web_form_request.first_used_on = now_datetime()
				web_form_request.save(ignore_permissions=True)
		elif web_form.has_web_form_permission(doctype, doc.name, "write"):
			# has_web_form_permission uses web-form rules (owner, website
			# permission, hooks) that are separate from Role Permissions.
			doc.save(ignore_permissions=True)
		else:
			# Standard DocType write permission applies.
			doc.save()

	else:
		# insert
		ignore_mandatory = True if (files or web_form.allow_incomplete) else False

		# login_required, key_required + valid web_form_request (for_update),
		# and allow_edit (updates) are enforced above; open forms allow Guest create.
		doc.insert(ignore_permissions=True, ignore_mandatory=ignore_mandatory)
		if web_form_request:
			web_form_request.append("references", {"link_doctype": doctype, "link_name": doc.name})
			if not web_form_request.first_used_on:
				web_form_request.first_used_on = now_datetime()
			# Request key validated above; Guest holders cannot save Web Form Request otherwise.
			web_form_request.save(ignore_permissions=True)

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

		# Persist attachment field URLs on a document already authorized above.
		doc.save(ignore_permissions=True)

	if files_to_delete:
		for f in files_to_delete:
			if f:
				remove_file_by_url(f, doctype=doctype, name=doc.name)

	if web_form.anonymous and frappe.session.user == "Guest" and user:
		frappe.session.user = user

	frappe.flags.web_form_doc = doc
	return doc


@public(group="Website")
@frappe.whitelist(methods=["POST", "DELETE"], allow_guest=True)
@rate_limit(key="web_form_name", limit=10, seconds=60)
def delete_web_form_document(
	web_form_name: str, docname: str | int, web_form_request_key: str | None = None
) -> None:
	"""Delete a document that was created through a web form.

	Allowed for the document owner, or for the holder of a valid Web Form
	Request key bound to the document, if the web form allows deletion.

	:param web_form_name: name of the Web Form
	:param docname: name of the document to be deleted
	:param web_form_request_key: key of a Web Form Request granting access
	"""
	web_form: WebForm = frappe.get_lazy_doc("Web Form", web_form_name)
	web_form_request: "WebFormRequest | None" = web_form.get_web_form_request(
		web_form_request_key,
		docname=docname,
		for_update=True,
		allow_used=True,
	)

	if (
		not web_form.allow_delete
		or (frappe.session.user == "Guest" and web_form.login_required)
		or (frappe.session.user == "Guest" and not web_form_request)
	):
		frappe.throw(_("Not Allowed"), frappe.PermissionError)

	owner = frappe.db.get_value(web_form.doc_type, docname, "owner")
	if web_form_request or frappe.session.user == owner:
		if web_form_request:
			# Drop the matching reference row before deleting the bound document
			# so Frappe's link-integrity check doesn't block the cascade. If
			# delete_doc fails, the framework rolls back the transaction.
			web_form_request.remove(web_form_request.find_reference(docname))
			if not web_form_request.first_used_on:
				web_form_request.first_used_on = now_datetime()
			# Key binding to docname verified above; update references before cascade delete.
			web_form_request.save(ignore_permissions=True)

		# allow_delete, guest/login/key gating, and owner or key binding checked above.
		frappe.delete_doc(web_form.doc_type, docname, ignore_permissions=True)
	else:
		frappe.throw(_("Not Allowed"), frappe.PermissionError)


@public(group="Website")
@frappe.whitelist(methods=["POST", "DELETE"])
@rate_limit(key="web_form_name", limit=10, seconds=60)
def delete_web_form_documents(web_form_name: str, docnames: str | list) -> None:
	"""Delete multiple own documents that were created through a web form.

	:param web_form_name: name of the Web Form
	:param docnames: names of the documents to be deleted
	:raises frappe.PermissionError: If any of the documents is not owned by the
		session user or the web form does not allow deletion.
	"""
	web_form = frappe.get_lazy_doc("Web Form", web_form_name)

	docnames = frappe.parse_json(docnames)

	allowed_docnames = []
	restricted_docnames = []

	for docname in docnames:
		assert isinstance(docname, str | int)

		owner = frappe.db.get_value(web_form.doc_type, docname, "owner")
		if frappe.session.user == owner and web_form.allow_delete:
			allowed_docnames.append(docname)
		else:
			restricted_docnames.append(docname)

	for docname in allowed_docnames:
		# Only owner-owned docnames with allow_delete enabled reach this loop.
		frappe.delete_doc(web_form.doc_type, docname, ignore_permissions=True)

	if restricted_docnames:
		raise frappe.PermissionError(
			"You do not have permisssion to delete " + ", ".join(restricted_docnames)
		)


@public(group="Website")
@frappe.whitelist(allow_guest=True)
@frappe.read_only()
def get_web_form_filters(web_form_name: str) -> list:
	"""Return the web form fields that can be used as list view filters.

	:param web_form_name: name of the Web Form
	:return: The web form fields with `show_in_filter` set.
	"""
	web_form = frappe.get_doc("Web Form", web_form_name)
	return [field for field in web_form.web_form_fields if field.show_in_filter]


@public(group="Website")
@frappe.whitelist(allow_guest=True)
@rate_limit(key="web_form", limit=10, seconds=60)
@frappe.read_only()
def get_web_form_list(
	web_form: str,
	web_form_request_key: str,
	limit_start: int = 0,
	limit: int = 20,
	**kwargs: Any,
) -> list[dict]:
	"""Return documents bound to a Web Form Request key for the list view.

	The key authorises read access to exactly the documents recorded in its
	``references`` child table — no more, no less.

	:param web_form: name of the Web Form
	:param web_form_request_key: key of the Web Form Request
	:param limit_start: start the list at this index
	:param limit: number of documents to return (capped at 100)
	:param kwargs: filters on fields of the web form's doctype
	:return: The documents as dicts.
	"""
	web_form_doc: WebForm = frappe.get_lazy_doc("Web Form", web_form)
	if web_form_doc.login_required and frappe.session.user == "Guest":
		frappe.throw(_("You must login to use this form"), frappe.PermissionError)

	if not web_form_doc.show_list:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	web_form_request: "WebFormRequest | None" = web_form_doc.get_web_form_request(
		web_form_request_key,
		allow_used=True,
	)
	if not web_form_request:
		frappe.throw(_("Invalid Web Form Request"), frappe.PermissionError)

	reference_names = [row.link_name for row in web_form_request.references]
	if not reference_names:
		return []

	meta = frappe.get_meta(web_form_doc.doc_type)
	filters = {}
	for fieldname, raw_value in kwargs.items():
		if not meta.has_field(fieldname):
			continue
		try:
			filters[fieldname] = json.loads(raw_value)
		except (TypeError, ValueError):
			filters[fieldname] = raw_value

	filters["name"] = ["in", reference_names]

	fields = get_web_form_list_fields(web_form_doc, web_form_request_key)

	return frappe.get_list(
		web_form_doc.doc_type,
		fields=fields,
		filters=filters,
		limit_start=cint(limit_start),
		limit_page_length=min(cint(limit), 100),
		# Valid key + show_list verified above; filters restrict to request references.
		ignore_permissions=True,
		order_by="creation desc",
		distinct=True,
	)


@public(group="Website")
@frappe.whitelist(allow_guest=True)
@frappe.read_only()
def get_web_form_data(
	doctype: str,
	docname: str | None = None,
	web_form_name: str | None = None,
	web_form_request_key: str | None = None,
) -> dict:
	"""Return a web form's definition, and the bound document when editing.

	:param doctype: doctype of the web form's target document
	:param docname: name of the document to be edited, if any
	:param web_form_name: name of the Web Form
	:param web_form_request_key: key of a Web Form Request granting access
	:return: Dict with the `web_form` definition, the `doc` (when editing) and
		processed Table/Link field metadata.
	"""
	web_form = frappe.get_doc("Web Form", web_form_name)

	if web_form.login_required and frappe.session.user == "Guest":
		frappe.throw(_("Not Permitted"), frappe.PermissionError)

	if getattr(web_form, "key_required", False):
		web_form.get_web_form_request(
			web_form_request_key,
			docname=docname,
			allow_used=True,
		)

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
			field.fields = get_in_list_view_fields(
				field.options, web_form_name, web_form_request_key, docname
			)
			out.update({field.fieldname: field.fields})

		if field.fieldtype == "Link":
			process_link_field(field, web_form_name, web_form_request_key, docname)

	return out


# ---------------------------------------------------------------------------
# Comments and discussions
# ---------------------------------------------------------------------------


@public(group="Website")
@frappe.whitelist(allow_guest=True)
@rate_limit(limit=get_comment_rate_limit, seconds=60 * 60)
def add_comment(
	comment: str,
	comment_email: str,
	comment_by: str,
	reference_doctype: str,
	reference_name: str,
	route: str,
	web_form: str | None = None,
) -> str | bool | None:
	"""Add a published comment on a website page.

	Guests may only comment on Web Pages (or a doctype allowed by the
	`has_comment_permission` hook); logged-in users comment as themselves.

	:param comment: the comment text; links and email addresses are rejected
	:param comment_email: email of the commenter, overridden by the session user when logged in
	:param comment_by: display name of the commenter, overridden by the session user when logged in
	:param reference_doctype: doctype of the page/document being commented on
	:param reference_name: name of the page/document being commented on
	:param route: website route to clear from the cache so the comment shows up
	:param web_form: web form through which the comment was made, if any
	:return: The rendered comment HTML, or False if the comment was rejected.
	"""
	if frappe.session.user == "Guest":
		allowed_doctypes = ["Web Page"]
		comments_permission_config = frappe.get_hooks("has_comment_permission")
		guest_allowed = False
		if len(comments_permission_config):
			if comments_permission_config["doctype"]:
				allowed_doctypes.append(comments_permission_config["doctype"][0])
				check_permission_method = comments_permission_config["method"]
				guest_allowed = frappe.call(check_permission_method[0], ref_doctype=reference_doctype)
		if reference_doctype not in allowed_doctypes:
			return

		if not guest_allowed:
			frappe.throw(_("Please login to post a comment."), exc=frappe.AuthenticationError)
	else:
		# override with the logged-in user's identity to prevent spoofing;
		# guests must supply their own name/email in the request
		comment_email = frappe.session.user
		comment_by = frappe.get_value("User", frappe.session.user, "full_name")

	if not comment.strip():
		frappe.msgprint(_("The comment cannot be empty"))
		return False

	if URLS_COMMENT_PATTERN.search(comment) or EMAIL_PATTERN.search(comment):
		frappe.msgprint(_("Comments cannot have links or email addresses"))
		return False

	perm_flag = True
	doc = frappe.get_doc(reference_doctype, reference_name)
	if web_form:
		web_form = frappe.get_lazy_doc("Web Form", web_form)
		perm_flag = web_form.doc_type == reference_doctype and web_form.has_web_form_permission(
			reference_doctype, reference_name
		)
	elif not (frappe.session.user == "Guest" and guest_allowed):
		perm_flag = doc.has_permission()

	if not perm_flag:
		if frappe.session.user == "Guest":
			raise frappe.AuthenticationError
		raise frappe.PermissionError

	comment = doc.add_comment(text=clean_html(comment), comment_email=comment_email, comment_by=comment_by)

	comment.db_set("published", 1)

	# since comments are embedded in the page, clear the web cache
	if route:
		clear_cache(route)

	# revert with template if all clear (no backlinks)
	template = frappe.get_template("templates/includes/comments/comment.html")
	return template.render({"comment": comment.as_dict()})


@public(group="Website")
@frappe.whitelist()
def submit_discussion(
	doctype: str,
	docname: str | int,
	reply: str,
	title: str,
	topic_name: str | None = None,
	reply_name: str | None = None,
) -> str | None:
	"""Post or edit a reply in a website discussion, creating the topic if needed.

	:param doctype: doctype the discussion topic references
	:param docname: document the discussion topic references
	:param reply: the reply text
	:param title: title for a newly created topic
	:param topic_name: post the reply to this existing topic
	:param reply_name: edit this existing reply (own replies only)
	:return: Name of the topic, or None when editing a reply.
	"""
	from frappe.website.doctype.discussion_topic.discussion_topic import save_message

	if reply_name:
		doc = frappe.get_doc("Discussion Reply", reply_name)
		if doc.owner != frappe.session.user:
			frappe.throw(frappe._("You can only edit your own replies."), frappe.PermissionError)
		doc.reply = reply
		doc.save(ignore_permissions=True)
		return

	if topic_name:
		save_message(reply, topic_name)
		return topic_name

	topic = frappe.get_doc(
		{
			"doctype": "Discussion Topic",
			"title": title,
			"reference_doctype": doctype,
			"reference_docname": docname,
		}
	)
	topic.save(ignore_permissions=True)
	save_message(reply, topic.name)
	return topic.name


@public(group="Website")
@frappe.whitelist()
def delete_discussion_reply(reply_name: str) -> None:
	"""Delete one's own reply from a website discussion.

	:param reply_name: name of the Discussion Reply to be deleted
	"""
	owner = frappe.db.get_value("Discussion Reply", reply_name, "owner")
	if owner == frappe.session.user:
		frappe.delete_doc("Discussion Reply", reply_name)


# ---------------------------------------------------------------------------
# Page views
# ---------------------------------------------------------------------------


@public(group="Website")
@frappe.whitelist(allow_guest=True)
def make_view_log(
	referrer: str | None = None,
	browser: str | None = None,
	version: str | int | None = None,
	user_tz: str | None = None,
	source: str | None = None,
	campaign: str | None = None,
	medium: str | None = None,
	content: str | None = None,
	visitor_id: str | None = None,
) -> None:
	"""Record a page view for website analytics, if view tracking is enabled.

	The tracked path is taken from the request's Referer header.

	:param referrer: URL the visitor came from
	:param browser: browser name
	:param version: browser version
	:param user_tz: visitor's time zone
	:param source: UTM source
	:param campaign: UTM campaign
	:param medium: UTM medium
	:param content: UTM content
	:param visitor_id: client-generated identifier used to count unique visitors
	"""
	if not is_tracking_enabled():
		return

	# real path
	path = frappe.request.headers.get("Referer")

	if not frappe.utils.is_site_link(path):
		return

	path = urlparse(path).path

	request_dict = frappe.request.__dict__
	user_agent = request_dict.get("environ", {}).get("HTTP_USER_AGENT")

	if referrer:
		referrer = referrer.split("?", 1)[0]

	if path != "/" and path.startswith("/"):
		path = path[1:]

	if path.startswith(("api/", "app/", "assets/", "private/files/")):
		return

	is_unique = visitor_id and not bool(frappe.db.exists("Web Page View", {"visitor_id": visitor_id}))

	view = frappe.new_doc("Web Page View")
	view.path = path
	view.referrer = referrer
	view.browser = browser
	view.browser_version = version
	view.time_zone = user_tz
	view.user_agent = user_agent
	view.is_unique = is_unique
	view.source = source
	view.campaign = campaign
	view.medium = (medium or "").lower()
	view.content = content
	view.visitor_id = visitor_id

	try:
		view.deferred_insert()
	except Exception:
		frappe.clear_last_message()


@public(group="Website")
@frappe.whitelist()
@redis_cache(ttl=5 * 60)
def get_page_view_count(path: str) -> int:
	"""Return the number of recorded views of a website page.

	:param path: website route of the page
	:return: Number of recorded page views.
	"""
	return frappe.db.count("Web Page View", filters={"path": path})


# ---------------------------------------------------------------------------
# Contact, feedback and account-related guest actions
# ---------------------------------------------------------------------------


@public(group="Website")
@frappe.whitelist(allow_guest=True)
@rate_limit(limit=1000, seconds=60 * 60)
def send_contact_message(sender: str, message: str, subject: str = "Website Query") -> None:
	"""Send a message through the website contact form.

	Forwards the message per Contact Us Settings, sends an acknowledgement to
	the sender and records the message as a Communication.

	:param sender: email address of the sender
	:param message: the message text
	:param subject: subject line for the forwarded message
	"""
	doc = frappe.get_doc("Contact Us Settings", "Contact Us Settings")
	if doc.is_disabled:
		return

	sender = validate_email_address(sender, throw=True)

	message = escape_html(message)

	with suppress(frappe.OutgoingEmailError):
		if forward_to_email := frappe.db.get_single_value("Contact Us Settings", "forward_to_email"):
			frappe.sendmail(recipients=forward_to_email, reply_to=sender, content=message, subject=subject)

		reply = _(
			"""Thank you for reaching out to us. We will get back to you at the earliest.


Your query:

{0}"""
		).format(message)
		frappe.sendmail(
			recipients=sender,
			content=f"<div style='white-space: pre-wrap'>{reply}</div>",
			subject=_("We've received your query!"),
		)

	# for clearing outgoing email error message
	frappe.clear_last_message()

	system_language = frappe.db.get_single_value("System Settings", "language")
	# add to to-do ?
	frappe.get_doc(
		doctype="Communication",
		sender=sender,
		subject=_("New Message from Website Contact Page", system_language),
		sent_or_received="Received",
		content=message,
		status="Open",
	).insert(ignore_permissions=True)


@public(group="Website")
@frappe.whitelist(allow_guest=True)
@rate_limit(key="article", limit=5, seconds=60 * 60)
def add_help_article_feedback(article: str, helpful: str) -> None:
	"""Record whether a knowledge base article was helpful.

	:param article: name of the Help Article
	:param helpful: "No" counts as not helpful, anything else as helpful
	"""
	field = "not_helpful" if helpful == "No" else "helpful"

	value = cint(frappe.db.get_value("Help Article", article, field))
	frappe.db.set_value("Help Article", article, field, value + 1, update_modified=False)


@public(group="Website")
@frappe.whitelist(allow_guest=True)
def confirm_personal_data_deletion(email: str, name: str, host_name: str) -> None:
	"""Confirm a personal data deletion request from a signed email link.

	Verifies the request signature, moves the request to Pending Approval and
	notifies the System Managers.

	:param email: email address the deletion was requested for
	:param name: name of the Personal Data Deletion Request
	:param host_name: site the request was made on (informational, part of the signed link)
	"""
	if not verify_request():
		return

	doc = frappe.get_doc("Personal Data Deletion Request", name)
	host_name = frappe.utils.get_url()

	if doc.status == "Pending Verification":
		doc.status = "Pending Approval"
		doc.save(ignore_permissions=True)
		doc.notify_system_managers()
		frappe.db.commit()
		frappe.respond_as_web_page(
			_("Confirmed"),
			_("The process for deletion of {0} data associated with {1} has been initiated.").format(
				host_name, email
			),
			indicator_color="green",
		)

	else:
		frappe.respond_as_web_page(
			_("Link Expired"),
			_("This link has already been activated for verification."),
			indicator_color="red",
		)


@public(group="Website")
@frappe.whitelist(allow_guest=True)
def unsubscribe(doctype: str, name: str, email: str) -> None:
	"""Unsubscribe an email address from a conversation, from a signed email link.

	Verifies the request signature, records an Email Unsubscribe and responds
	with a confirmation page.

	:param doctype: reference doctype of the conversation
	:param name: reference document of the conversation
	:param email: email address to be unsubscribed
	"""
	from frappe.email.queue import return_unsubscribed_page

	if not frappe.in_test and not verify_request():
		return

	try:
		frappe.get_doc(
			{
				"doctype": "Email Unsubscribe",
				"email": email,
				"reference_doctype": doctype,
				"reference_name": name,
			}
		).insert(ignore_permissions=True)

	except frappe.DuplicateEntryError:
		frappe.db.rollback()

	else:
		frappe.db.commit()

	return_unsubscribed_page(email, doctype, name)
