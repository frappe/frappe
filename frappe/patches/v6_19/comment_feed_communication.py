from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.rename_doc import get_link_fields
from frappe.model.dynamic_links import dynamic_link_queries
from frappe.permissions import reset_perms

def execute():
	# comments stay comments in v12
	return

	frappe.reload_doctype("DocType")
	frappe.reload_doctype("Communication")
	reset_perms("Communication")

	migrate_comments()
	frappe.delete_doc("DocType", "Comment")
	# frappe.db.sql_ddl("drop table `tabComment`")

	migrate_feed()
	frappe.delete_doc("DocType", "Feed")
	# frappe.db.sql_ddl("drop table `tabFeed`")

	update_timeline_doc_for("Blogger")

def migrate_comments():
	from_fields = ""
	to_fields = ""

	if "reference_doctype" in frappe.db.get_table_columns("Comment"):
		from_fields = "reference_doctype as link_doctype, reference_name as link_name,"
		to_fields = "link_doctype, link_name,"

	# comments
	frappe.db.sql("""insert ignore into `tabCommunication` (
			subject,
			content,
			sender,
			sender_full_name,
			comment_type,
			communication_date,
			reference_doctype,
			reference_name,
			{to_fields}

			name,
			user,
			owner,
			creation,
			modified_by,
			modified,
			status,
			sent_or_received,
			communication_type,
			seen
		)
		select
			substring(comment, 1, 100) as subject,
			comment as content,
			comment_by as sender,
			comment_by_fullname as sender_full_name,
			comment_type,
			ifnull(timestamp(comment_date, comment_time), creation) as communication_date,
			comment_doctype as reference_doctype,
			comment_docname as reference_name,
			{from_fields}

			name,
			owner as user,
			owner,
			creation,
			modified_by,
			modified,
			'Linked' as status,
			'Sent' as sent_or_received,
			'Comment' as communication_type,
			1 as seen
		from `tabComment` where comment_doctype is not null and comment_doctype not in ('Message', 'My Company')"""
			.format(to_fields=to_fields, from_fields=from_fields))

	# chat and assignment notifications
	frappe.db.sql("""insert ignore into `tabCommunication` (
			subject,
			content,
			sender,
			sender_full_name,
			comment_type,
			communication_date,
			reference_doctype,
			reference_name,
			{to_fields}

			name,
			user,
			owner,
			creation,
			modified_by,
			modified,
			status,
			sent_or_received,
			communication_type,
			seen
		)
		select
			case
				when parenttype='Assignment' then %(assignment)s
				else substring(comment, 1, 100)
				end
				as subject,
			comment as content,
			comment_by as sender,
			comment_by_fullname as sender_full_name,
			comment_type,
			ifnull(timestamp(comment_date, comment_time), creation) as communication_date,
			'User' as reference_doctype,
			comment_docname as reference_name,
			{from_fields}

			name,
			owner as user,
			owner,
			creation,
			modified_by,
			modified,
			'Linked' as status,
			'Sent' as sent_or_received,
			case
				when parenttype='Assignment' then 'Notification'
				else 'Chat'
				end
				as communication_type,
			1 as seen
		from `tabComment` where comment_doctype in ('Message', 'My Company')"""
			.format(to_fields=to_fields, from_fields=from_fields), {"assignment": _("Assignment")})

def migrate_feed():
	# migrate delete feed
	for doctype in frappe.db.sql("""select distinct doc_type from `tabFeed` where subject=%(deleted)s""", {"deleted": _("Deleted")}):
		frappe.db.sql("""insert ignore into `tabCommunication` (
				subject,
				sender,
				sender_full_name,
				comment_type,
				communication_date,
				reference_doctype,

				name,
				user,
				owner,
				creation,
				modified_by,
				modified,
				status,
				sent_or_received,
				communication_type,
				seen
			)
			select
				concat_ws(" ", %(_doctype)s, doc_name) as subject,
				owner as sender,
				full_name as sender_full_name,
				'Deleted' as comment_type,
				creation as communication_date,
				doc_type as reference_doctype,

				name,
				owner as user,
				owner,
				creation,
				modified_by,
				modified,
				'Linked' as status,
				'Sent' as sent_or_received,
				'Comment' as communication_type,
				1 as seen
			from `tabFeed` where subject=%(deleted)s and doc_type=%(doctype)s""", {
				"deleted": _("Deleted"),
				"doctype": doctype,
				"_doctype": _(doctype)
			})

	# migrate feed type login or empty
	frappe.db.sql("""insert ignore into `tabCommunication` (
			subject,
			sender,
			sender_full_name,
			comment_type,
			communication_date,
			reference_doctype,
			reference_name,

			name,
			user,
			owner,
			creation,
			modified_by,
			modified,
			status,
			sent_or_received,
			communication_type,
			seen
		)
		select
			subject,
			owner as sender,
			full_name as sender_full_name,
			case
				when feed_type='Login' then 'Info'
				else 'Updated'
				end as comment_type,
			creation as communication_date,
			doc_type as reference_doctype,
			doc_name as reference_name,

			name,
			owner as user,
			owner,
			creation,
			modified_by,
			modified,
			'Linked' as status,
			'Sent' as sent_or_received,
			'Comment' as communication_type,
			1 as seen
		from `tabFeed` where (feed_type in ('Login', '') or feed_type is null)""")

def update_timeline_doc_for(timeline_doctype):
	"""NOTE: This method may be used by other apps for patching. It also has COMMIT after each update."""

	# find linked doctypes
	# link fields
	update_for_linked_docs(timeline_doctype)

	# dynamic link fields
	update_for_dynamically_linked_docs(timeline_doctype)

def update_for_linked_docs(timeline_doctype):
	for df in get_link_fields(timeline_doctype):
		if df.issingle:
			continue

		reference_doctype = df.parent

		if not is_valid_timeline_doctype(reference_doctype, timeline_doctype):
			continue

		for doc in frappe.get_all(reference_doctype, fields=["name", df.fieldname]):
			timeline_name = doc.get(df.fieldname)
			update_communication(timeline_doctype, timeline_name, reference_doctype, doc.name)

def update_for_dynamically_linked_docs(timeline_doctype):
	dynamic_link_fields = []
	for query in dynamic_link_queries:
		for df in frappe.db.sql(query, as_dict=True):
			dynamic_link_fields.append(df)

	for df in dynamic_link_fields:
		reference_doctype = df.parent

		if not is_valid_timeline_doctype(reference_doctype, timeline_doctype):
			continue

		try:
			docs = frappe.get_all(reference_doctype, fields=["name", df.fieldname],
				filters={ df.options: timeline_doctype })
		except frappe.db.SQLError as e:
			if frappe.db.is_table_missing(e):
				# single
				continue
			else:
				raise

		for doc in docs:
			timeline_name = doc.get(df.fieldname)
			update_communication(timeline_doctype, timeline_name, reference_doctype, doc.name)

def update_communication(timeline_doctype, timeline_name, reference_doctype, reference_name):
	if not timeline_name:
		return

	frappe.db.sql("""update `tabCommunication` set timeline_doctype=%(timeline_doctype)s, timeline_name=%(timeline_name)s
		where (reference_doctype=%(reference_doctype)s and reference_name=%(reference_name)s)
			and (timeline_doctype is null or timeline_doctype='')
			and (timeline_name is null or timeline_name='')""", {
				"timeline_doctype": timeline_doctype,
				"timeline_name": timeline_name,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name
			})

	frappe.db.commit()

def is_valid_timeline_doctype(reference_doctype, timeline_doctype):
	# for reloading timeline_field
	frappe.reload_doctype(reference_doctype)

	# make sure the timeline field's doctype is same as timeline doctype
	meta = frappe.get_meta(reference_doctype)
	if not meta.timeline_field:
		return False

	doctype = meta.get_link_doctype(meta.timeline_field)
	if doctype != timeline_doctype:
		return False


	return True
