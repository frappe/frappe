# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts
import nts.utils
from nts import _
from nts.model import log_types
from nts.query_builder import DocType
from nts.utils import get_url_to_form


@nts.whitelist()
def update_follow(doctype: str, doc_name: str, following: bool):
	if following:
		return follow_document(doctype, doc_name, nts.session.user)
	else:
		return unfollow_document(doctype, doc_name, nts.session.user)


@nts.whitelist()
def follow_document(doctype, doc_name, user):
	"""
	param:
	Doctype name
	doc name
	user email

	condition:
	avoided for some doctype
	follow only if track changes are set to 1
	"""
	if (
		doctype
		in (
			"Communication",
			"ToDo",
			"Email Unsubscribe",
			"File",
			"Comment",
			"Email Account",
			"Email Domain",
		)
		or doctype in log_types
	):
		return

	if (not nts.get_meta(doctype).track_changes) or user == "Administrator":
		return

	if not nts.db.get_value("User", user, "document_follow_notify", ignore=True, cache=True):
		return

	if not is_document_followed(doctype, doc_name, user):
		doc = nts.new_doc("Document Follow")
		doc.update({"ref_doctype": doctype, "ref_docname": doc_name, "user": user})
		doc.save()
		return doc


@nts.whitelist()
def unfollow_document(doctype, doc_name, user):
	doc = nts.get_all(
		"Document Follow",
		filters={"ref_doctype": doctype, "ref_docname": doc_name, "user": user},
		fields=["name"],
		limit=1,
	)
	if doc:
		nts.delete_doc("Document Follow", doc[0].name)
		return 1
	return 0


def get_message(doc_name, doctype, frequency, user):
	activity_list = get_version(doctype, doc_name, frequency, user) + get_comments(
		doctype, doc_name, frequency, user
	)
	return sorted(activity_list, key=lambda k: k["time"], reverse=True)


def send_email_alert(receiver, docinfo, timeline):
	if receiver:
		nts.sendmail(
			subject=_("Document Follow Notification"),
			recipients=[receiver],
			template="document_follow",
			args={
				"docinfo": docinfo,
				"timeline": timeline,
			},
		)


def send_document_follow_mails(frequency):
	"""
	param:
	frequency for sanding mails

	task:
	set receiver according to frequency
	group document list according to user
	get changes, activity, comments on doctype
	call method to send mail
	"""

	user_list = get_user_list(frequency)

	for user in user_list:
		message, valid_document_follows = get_message_for_user(frequency, user)
		if message:
			send_email_alert(user, valid_document_follows, message)
			# send an email if we have already spent resources creating	the message
			# nosemgrep
			nts.db.commit()


def get_user_list(frequency):
	DocumentFollow = DocType("Document Follow")
	User = DocType("User")
	return (
		nts.qb.from_(DocumentFollow)
		.join(User)
		.on(DocumentFollow.user == User.name)
		.where(User.document_follow_notify == 1)
		.where(User.document_follow_frequency == frequency)
		.select(DocumentFollow.user)
		.groupby(DocumentFollow.user)
	).run(pluck="user")


def get_message_for_user(frequency, user):
	message = []
	latest_document_follows = get_document_followed_by_user(user)
	valid_document_follows = []

	for document_follow in latest_document_follows:
		content = get_message(document_follow.ref_docname, document_follow.ref_doctype, frequency, user)
		if content:
			message = message + content
			valid_document_follows.append(
				{
					"reference_docname": document_follow.ref_docname,
					"reference_doctype": document_follow.ref_doctype,
					"reference_url": get_url_to_form(
						document_follow.ref_doctype, document_follow.ref_docname
					),
				}
			)
	return message, valid_document_follows


def get_document_followed_by_user(user):
	DocumentFollow = DocType("Document Follow")
	# at max 20 documents are sent for each user
	return (
		nts.qb.from_(DocumentFollow)
		.where(DocumentFollow.user == user)
		.select(DocumentFollow.ref_doctype, DocumentFollow.ref_docname)
		.orderby(DocumentFollow.modified)
		.limit(20)
	).run(as_dict=True)


def get_version(doctype, doc_name, frequency, user):
	timeline = []
	version = nts.get_all(
		"Version",
		filters=[
			["ref_doctype", "=", doctype],
			["docname", "=", doc_name],
			*_get_filters(frequency, user),
		],
		fields=["data", "modified", "modified_by"],
	)
	if version:
		for v in version:
			change = nts.parse_json(v.data)
			time = nts.utils.format_datetime(v.modified, "hh:mm a")
			timeline_items = []
			if change.changed:
				timeline_items = get_field_changed(change.changed, time, doctype, doc_name, v)
			if change.row_changed:
				timeline_items = get_row_changed(change.row_changed, time, doctype, doc_name, v)
			if change.added:
				timeline_items = get_added_row(change.added, time, doctype, doc_name, v)

			timeline = timeline + timeline_items

	return timeline


def get_comments(doctype, doc_name, frequency, user):
	from nts.core.utils import html2text

	timeline = []
	comments = nts.get_all(
		"Comment",
		filters=[
			["reference_doctype", "=", doctype],
			["reference_name", "=", doc_name],
			*_get_filters(frequency, user),
		],
		fields=["content", "modified", "modified_by", "comment_type"],
	)
	for comment in comments:
		if comment.comment_type == "Like":
			by = f""" By : <b>{comment.modified_by}<b>"""
		elif comment.comment_type == "Comment":
			by = f"""Commented by : <b>{comment.modified_by}<b>"""
		else:
			by = ""

		time = nts.utils.format_datetime(comment.modified, "hh:mm a")
		timeline.append(
			{
				"time": comment.modified,
				"data": {"time": time, "comment": html2text(str(comment.content)), "by": by},
				"doctype": doctype,
				"doc_name": doc_name,
				"type": "comment",
			}
		)
	return timeline


def is_document_followed(doctype, doc_name, user):
	return nts.db.exists(
		"Document Follow", {"ref_doctype": doctype, "ref_docname": str(doc_name), "user": user}
	)


@nts.whitelist()
def get_follow_users(doctype, doc_name):
	return nts.get_all(
		"Document Follow", filters={"ref_doctype": doctype, "ref_docname": doc_name}, fields=["user"]
	)


def get_row_changed(row_changed, time, doctype, doc_name, v):
	from nts.core.utils import html2text

	items = []
	for d in row_changed:
		d[2] = d[2] if d[2] else " "
		d[0] = d[0] if d[0] else " "
		d[3][0][1] = d[3][0][1] if d[3][0][1] else " "
		items.append(
			{
				"time": v.modified,
				"data": {
					"time": time,
					"table_field": d[0],
					"row": str(d[1]),
					"field": d[3][0][0],
					"from": html2text(str(d[3][0][1])),
					"to": html2text(str(d[3][0][2])),
				},
				"doctype": doctype,
				"doc_name": doc_name,
				"type": "row changed",
				"by": v.modified_by,
			}
		)
	return items


def get_added_row(added, time, doctype, doc_name, v):
	return [
		{
			"time": v.modified,
			"data": {"to": d[0], "time": time},
			"doctype": doctype,
			"doc_name": doc_name,
			"type": "row added",
			"by": v.modified_by,
		}
		for d in added
	]


def get_field_changed(changed, time, doctype, doc_name, v):
	from nts.core.utils import html2text

	items = []
	for d in changed:
		d[1] = d[1] if d[1] else " "
		d[2] = d[2] if d[2] else " "
		d[0] = d[0] if d[0] else " "
		items.append(
			{
				"time": v.modified,
				"data": {
					"time": time,
					"field": d[0],
					"from": html2text(str(d[1])),
					"to": html2text(str(d[2])),
				},
				"doctype": doctype,
				"doc_name": doc_name,
				"type": "field changed",
				"by": v.modified_by,
			}
		)
	return items


def send_hourly_updates():
	send_document_follow_mails("Hourly")


def send_daily_updates():
	send_document_follow_mails("Daily")


def send_weekly_updates():
	send_document_follow_mails("Weekly")


def _get_filters(frequency, user):
	filters = [
		["modified_by", "!=", user],
	]

	if frequency == "Weekly":
		filters += [
			["modified", ">", nts.utils.add_days(nts.utils.nowdate(), -7)],
			["modified", "<", nts.utils.nowdate()],
		]

	elif frequency == "Daily":
		filters += [
			["modified", ">", nts.utils.add_days(nts.utils.nowdate(), -1)],
			["modified", "<", nts.utils.nowdate()],
		]

	elif frequency == "Hourly":
		filters += [
			["modified", ">", nts.utils.add_to_date(nts.utils.now_datetime(), hours=-1)],
			["modified", "<", nts.utils.now_datetime()],
		]

	return filters
