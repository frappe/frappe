"""Write handlers for the collaboration parts of a v2 document route.

`POST /document/<doctype>/<name>/<part>` adds, `DELETE .../<part>/<key>` removes and
`PATCH .../comments/<name>` edits. Each answers with the refreshed part in the read's shape.
"""

import html
import re

import frappe
import frappe.share
from frappe import _
from frappe.api.include import DOCUMENT_PARTS, USER_ROW_KEY, USERS_PART, UnknownPartError, users_named_by
from frappe.desk.doctype.favourite.favourite import toggle_favourite
from frappe.desk.doctype.tag.tag import add_tag, remove_tag
from frappe.desk.form import assign_to
from frappe.desk.form.document_follow import follow_document, unfollow_document
from frappe.desk.form.utils import add_comment, delete_comment, update_comment
from frappe.model.document import Document
from frappe.utils import cint, get_fullname

EVERYONE = "everyone"
MAX_ATTACHMENTS = 10
INLINE_MEDIA = re.compile(r'<(?:img|video|source)\b[^>]*?\ssrc\s*=\s*["\']([^"\']+)["\']')


def add(doctype: str, name: str, part: str) -> dict:
	"""Add to `part` from the request body; answers with the refreshed part, and a comment's `added` name."""
	doc = load(doctype, name, part)
	added = ADD[part](doc, read_body(part, adding=True))
	response = refreshed(doc, part)
	if added:
		response["added"] = added
	return response


def remove(doctype: str, name: str, part: str, key: str | None = None) -> dict:
	"""Remove `key` from `part` of the document; the caller's own row for the keyless parts."""
	doc = load(doctype, name, part)
	if (key is None) != (part in KEYLESS_PARTS):
		raise InvalidRequestError(
			_("'{0}' takes no key").format(part) if key else _("'{0}' needs a key").format(part)
		)
	REMOVE[part](doc, key)
	return refreshed(doc, part)


def update(doctype: str, name: str, part: str, key: str) -> dict:
	"""Edit `key` of `part` from the request body; only comments can be edited."""
	doc = load(doctype, name, part)
	if part != "comments":
		raise frappe.ValidationError(_("PATCH is only valid for comments"))
	update_comment(comment_of(doc, key).name, read_body(part)["content"])
	return refreshed(doc, part)


class InvalidRequestError(frappe.ValidationError):
	http_status_code = 417


def load(doctype: str, name: str, part: str) -> Document:
	if part not in PART_RIGHT:
		raise UnknownPartError(part, PART_RIGHT)
	doc = frappe.get_doc(doctype, name)
	doc.check_permission(PART_RIGHT[part])
	return doc


def read_body(part: str, adding: bool = False) -> dict:
	body = frappe.form_dict
	for key in REQUIRED_BODY[part]:
		value = body.get(key)
		if adding and attachment_only(part, key, body):
			continue
		if not isinstance(value, str) or not value.strip():
			raise InvalidRequestError(_("'{0}' must be a non-empty string").format(key))
	for key in OPTIONAL_BODY.get(part, ()):
		if key in body:
			check_optional(key, body[key])
	return body


def attachment_only(part: str, key: str, body: dict) -> bool:
	"""Whether a new comment may leave `content` empty because it carries attachments."""
	attachments, content = body.get("attachments"), body.get(key, "")
	on_comment_content = part == "comments" and key == "content"
	return (
		on_comment_content
		and isinstance(content, str)
		and isinstance(attachments, list)
		and bool(attachments)
	)


def check_optional(key: str, value) -> None:
	if key not in LIST_KEYS:
		if not isinstance(value, str):
			raise InvalidRequestError(_("'{0}' must be a string").format(key))
	elif not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
		raise InvalidRequestError(_("'{0}' must be a list of names").format(key))


def refreshed(doc: Document, part: str) -> dict:
	rows = DOCUMENT_PARTS[part](doc)
	response = {part: rows}
	if part in USER_ROW_KEY:
		response[USERS_PART] = users_named_by(doc, {part: rows})
	return response


def add_assignment(doc: Document, body: dict) -> None:
	args = {"assign_to": [body["user"]], "doctype": doc.doctype, "name": doc.name}
	for key in ("description", "priority", "date"):
		if body.get(key):
			args[key] = body[key]
	assign_to.add(args)


def remove_assignment(doc: Document, user: str) -> None:
	assign_to.remove(doc.doctype, doc.name, user)


def add_share(doc: Document, body: dict) -> None:
	if "read" in body and not cint(body["read"]):
		raise InvalidRequestError(_("A share always grants read"))
	user, everyone = share_target(body["user"])
	rights = {right: cint(body.get(right)) for right in ("write", "submit", "share")}
	frappe.share.add(doc.doctype, doc.name, user=user, everyone=everyone, **rights)


def remove_share(doc: Document, user: str) -> None:
	user, everyone = share_target(user)
	frappe.share.set_docshare_permission(doc.doctype, doc.name, user, "read", value=0, everyone=everyone)


def share_target(user: str) -> tuple[str | None, int]:
	return (None, 1) if user == EVERYONE else (user, 0)


def add_a_tag(doc: Document, body: dict) -> None:
	if "," in body["tag"]:
		raise InvalidRequestError(_("A tag cannot contain a comma"))
	add_tag(body["tag"], doc.doctype, doc.name)


def remove_a_tag(doc: Document, tag: str) -> None:
	remove_tag(tag, doc.doctype, doc.name)


def add_favourite(doc: Document, body: dict) -> None:
	toggle_favourite(doc.doctype, doc.name, add=True)


def remove_favourite(doc: Document, key: None) -> None:
	toggle_favourite(doc.doctype, doc.name, add=False)


def add_follow(doc: Document, body: dict) -> None:
	follow_document(doc.doctype, doc.name)


def remove_follow(doc: Document, key: None) -> None:
	unfollow_document(doc.doctype, doc.name)


def add_a_comment(doc: Document, body: dict) -> str:
	files = files_to_link(body.get("attachments") or [])
	comment = add_comment(
		doc.doctype, doc.name, body.get("content") or "", frappe.session.user, get_fullname()
	)
	attach_files(files, "Comment", comment.name)
	# after the attachments are linked, so they are no longer unattached and stay on the Comment
	attach_inline_media(doc, comment.content)
	return comment.name


def files_to_link(names: list[str]) -> list[str]:
	"""The caller's own unattached Files; any other name is refused."""
	if len(names) > MAX_ATTACHMENTS:
		raise InvalidRequestError(_("A comment takes at most {0} attachments").format(MAX_ATTACHMENTS))
	names = list(dict.fromkeys(names))
	fields = ["name", "owner", "attached_to_doctype", "is_folder"]
	rows = frappe.get_all("File", filters={"name": ("in", names)}, fields=fields) if names else []
	if len(rows) != len(names) or not all(linkable(row) for row in rows):
		raise frappe.PermissionError(_("Only your own unattached files can be added to a comment"))
	return names


def linkable(file: dict) -> bool:
	return file.owner == frappe.session.user and not file.attached_to_doctype and not file.is_folder


def attach_inline_media(doc: Document, content: str) -> None:
	"""Attach the caller's unattached Files shown inline in `content` to `doc`, as desk comments do."""
	urls = list({html.unescape(url) for url in INLINE_MEDIA.findall(content or "")})
	if not urls:
		return
	filters = {
		"file_url": ("in", urls),
		"owner": frappe.session.user,
		"attached_to_doctype": ("is", "not set"),
	}
	attach_files(frappe.get_all("File", filters=filters, pluck="name"), doc.doctype, doc.name)


def attach_files(names: list[str], doctype: str, name: str) -> None:
	"""Attach the Files `names` to `doctype` `name` in one write; the caller has checked them."""
	if names:
		values = {"attached_to_doctype": doctype, "attached_to_name": name}
		frappe.db.set_value("File", {"name": ("in", names)}, values)


def remove_comment(doc: Document, name: str) -> None:
	delete_comment(comment_of(doc, name).name)


def comment_of(doc: Document, name: str) -> Document:
	"""The comment `name`, which must belong to `doc`."""
	comment = frappe.get_doc("Comment", name)
	on_doc = comment.reference_doctype == doc.doctype and comment.reference_name == str(doc.name)
	if not on_doc:
		raise frappe.DoesNotExistError(_("Comment {0} is not on {1} {2}").format(name, doc.doctype, doc.name))
	return comment


# the permission each part checks before the framework call adds its own
PART_RIGHT = {
	"assignments": "write",
	"shares": "share",
	"tags": "write",
	"favourites": "read",
	"follows": "read",
	"comments": "read",
}
KEYLESS_PARTS = ("favourites", "follows")
OPTIONAL_BODY = {"assignments": ("description", "priority", "date"), "comments": ("attachments",)}
LIST_KEYS = ("attachments",)
REQUIRED_BODY = {
	"assignments": ("user",),
	"shares": ("user",),
	"tags": ("tag",),
	"favourites": (),
	"follows": (),
	"comments": ("content",),
}
ADD = {
	"assignments": add_assignment,
	"shares": add_share,
	"tags": add_a_tag,
	"favourites": add_favourite,
	"follows": add_follow,
	"comments": add_a_comment,
}
REMOVE = {
	"assignments": remove_assignment,
	"shares": remove_share,
	"tags": remove_a_tag,
	"favourites": remove_favourite,
	"follows": remove_follow,
	"comments": remove_comment,
}
