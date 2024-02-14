from frappe.desk.doctype.comment.comment import (
	Comment,
	get_comments_from_parent,
	on_doctype_update,
	update_comment_in_doc,
	update_comments_in_parent,
)
from frappe.utils.deprecations import deprecated

Comment.__new__ = deprecated(Comment.__new__, "moved to frappe.desk.doctype.comment.comment.Comment")
on_doctype_update = deprecated(
	on_doctype_update, "moved to frappe.desk.doctype.comment.comment.on_doctype_update"
)
update_comment_in_doc = deprecated(
	update_comment_in_doc, "moved to frappe.desk.doctype.comment.comment.update_comment_in_doc"
)
get_comments_from_parent = deprecated(
	get_comments_from_parent, "moved to frappe.desk.doctype.comment.comment.get_comments_from_parent"
)
update_comments_in_parent = deprecated(
	update_comments_in_parent, "moved to frappe.desk.doctype.comment.comment.update_comments_in_parent"
)
