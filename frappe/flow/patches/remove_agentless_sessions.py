import frappe

from flow.flow.doctype.flow_session.flow_session import _delete_attachment_files, _purge_attachment_chunks


# Sessions of the removed in-process code agents had no Flow Agent and no flow server copy.
# The link is required now, so they go with their runs and transcript.
def execute():
	sessions = frappe.get_all("Flow Session", filters={"agent": ["is", "not set"]}, pluck="name")
	if not sessions:
		return
	frappe.db.delete("Flow Run", {"session": ["in", sessions]})
	frappe.db.delete("Flow Session Message", {"parent": ["in", sessions]})
	_delete_attachment_files(sessions)
	frappe.db.delete("Flow Session Attachment", {"parent": ["in", sessions]})
	frappe.db.delete("Flow Session", {"name": ["in", sessions]})
	_purge_attachment_chunks(sessions)
