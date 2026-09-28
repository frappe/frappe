# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import DocType
from frappe.utils import unique

TAG_COLOR_NAMES = (
	"Gray",
	"Black",
	"Blue",
	"Green",
	"Red",
	"Pink",
	"Orange",
	"Amber",
	"Yellow",
	"Cyan",
	"Teal",
	"Violet",
	"Purple",
)


class Tag(Document):
	_DOCTYPE_NAME = "Tag"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
	# end: auto-generated types

	def validate(self):
		color = self.get("color")
		if color and color not in TAG_COLOR_NAMES:
			frappe.throw(_("Invalid tag color"))
		self.validate_apps()

	def validate_apps(self):
		apps = [row.app_name for row in self.get("apps", []) if row.app_name]
		if len(apps) != len(set(apps)):
			frappe.throw(_("Each app can only be added once"))
		invalid_apps = set(apps) - set(frappe.get_active_apps())
		if invalid_apps:
			frappe.throw(_("These apps are not installed: {0}").format(", ".join(sorted(invalid_apps))))


def check_user_tags(dt):
	"if the user does not have a tags column, then it creates one"
	try:
		doctype = DocType(dt)
		frappe.qb.from_(doctype).select(doctype._user_tags).limit(1).run()
	except Exception as e:
		if frappe.db.is_missing_column(e):
			DocTags(dt).setup()


@frappe.whitelist()
def add_tag(tag: str, dt: str, dn: str, color: str | None = None):
	"adds a new tag to a record, and creates the Tag master"
	DocTags(dt).add(dn, tag)

	return tag


@frappe.whitelist()
def add_tags(tags: str | list[str], dt: str, docs: str | list[str], color: str | None = None):
	"adds a new tag to a record, and creates the Tag master"

	if not frappe.get_cached_value("User", frappe.session.user, "bulk_actions"):
		frappe.throw(_("You are not allowed to perform bulk actions"), frappe.PermissionError)

	tags = frappe.parse_json(tags)
	docs = frappe.parse_json(docs)
	for doc in docs:
		for tag in tags:
			DocTags(dt).add(doc, tag)


@frappe.whitelist()
def remove_tag(tag: str, dt: str, dn: str):
	"removes tag from the record"
	DocTags(dt).remove(dn, tag)


@frappe.whitelist()
def get_tagged_docs(doctype: str, tag: str):
	frappe.has_permission(doctype, throw=True)
	doctype = DocType(doctype)
	return (frappe.qb.from_(doctype).where(doctype._user_tags.like(tag)).select(doctype.name)).run()


@frappe.whitelist()
def get_tags(doctype: str, txt: str, app: str = "frappe"):
	tag = frappe.get_list("Tag", filters=[["name", "like", f"%{txt}%"]])
	tags = [t.name for t in tag]
	return sorted(
		name
		for name in set(tags)
		if name and txt.casefold() in name.casefold() and tag_belongs_to_app(name, app)
	)


@frappe.whitelist(methods=["GET"])
def get_tags_for_app(app: str, txt: str = ""):
	"""Return visible tags and colors for one installed app."""
	validate_tag_app(app)
	fields = ["name"]
	if frappe.get_meta("Tag").has_field("color"):
		fields.append("color")
	tags = frappe.get_list("Tag", filters=[["name", "like", f"%{txt}%"]], fields=fields, order_by="name asc")
	return [
		{"name": tag.name, "color": tag.get("color")} for tag in tags if tag_belongs_to_app(tag.name, app)
	]


@frappe.whitelist(methods=["POST"])
def update_document_tags(
	doctype: str,
	docname: str,
	app: str,
	added: list[dict] | None = None,
	removed: list[str] | None = None,
):
	"""Apply a batch of tag changes for an app, preserving global tag identity."""
	validate_tag_app(app)
	frappe.has_permission(doctype, "write", doc=docname, throw=True)
	doc = frappe.get_doc(doctype, docname)
	doc.check_permission("write")
	doc_tags = DocTags(doctype)
	for tag in added or []:
		label = (tag.get("name") or "").strip()
		if not label or "," in label:
			frappe.throw(_("Tag must have a name and cannot contain commas"))
		doc_tags.add(docname, label, app=app, color=tag.get("color"))
	for tag in removed or []:
		doc_tags.remove(docname, tag)
	return frappe.db.get_value(doctype, docname, "_user_tags") or ""


def validate_tag_app(app: str) -> None:
	"""Ensure an app-scoped tag request names an installed app."""
	if app not in frappe.get_active_apps():
		frappe.throw(_("Application is not installed"), frappe.ValidationError)


def tag_belongs_to_app(tag_name: str, app: str) -> bool:
	"""Whether a tag is shared with the given app; legacy unscoped tags belong to Desk."""
	if not frappe.get_meta("Tag").has_field("apps"):
		return app == "frappe"
	apps = frappe.get_all(
		"Tag App",
		filters={"parent": tag_name, "parenttype": "Tag", "parentfield": "apps"},
		pluck="app_name",
	)
	return app in apps or (app == "frappe" and not apps)


class DocTags:
	"""Tags for a particular doctype"""

	def __init__(self, dt):
		self.dt = dt

	def get_tag_fields(self):
		"""Return `tag_fields` property."""
		return frappe.db.get_value("DocType", self.dt, "tag_fields")

	def get_tags(self, dn):
		"""Return tag for a particular item."""
		return (frappe.db.get_value(self.dt, dn, "_user_tags", ignore=1) or "").strip()

	def add(self, dn, tag, app: str = "frappe", color: str | None = None):
		"""Add a new user tag."""
		tag_doc = frappe.get_doc("Tag", tag) if frappe.db.exists("Tag", tag) else None
		if not tag_doc:
			frappe.has_permission("Tag", "create", throw=True)
			values = {"doctype": "Tag", "name": tag}
			if frappe.get_meta("Tag").has_field("color"):
				values["color"] = color
			tag_doc = frappe.get_doc(values)
			if frappe.get_meta("Tag").has_field("apps"):
				tag_doc.append("apps", {"app_name": app or "frappe"})
			tag_doc.insert()
		else:
			apps = {row.app_name for row in tag_doc.get("apps", []) if row.app_name}
			if frappe.get_meta("Tag").has_field("apps") and not apps:
				tag_doc.append("apps", {"app_name": "frappe"})
				apps.add("frappe")
			if frappe.get_meta("Tag").has_field("apps") and app and app not in apps:
				tag_doc.check_permission("write")
				tag_doc.append("apps", {"app_name": app})
				tag_doc.save()

		tl = self.get_tags(dn).split(",")
		if tag not in tl:
			tl.append(tag)
			self.update(dn, tl)

	def remove(self, dn, tag):
		"""Remove a user tag."""
		tl = self.get_tags(dn).split(",")
		self.update(dn, filter(lambda x: x.lower() != tag.lower(), tl))

	def remove_all(self, dn):
		"""Remove all user tags (call before delete)."""
		self.update(dn, [])

	def update(self, dn, tl):
		"""Update the `_user_tag` column in the table."""

		if not tl:
			tags = ""
		else:
			tl = unique(filter(lambda x: x, tl))
			tags = ",".join(tl)
		old_tags = {tag for tag in self.get_tags(dn).split(",") if tag}
		new_tags = {tag for tag in tags.split(",") if tag}
		try:
			frappe.db.set_value(self.dt, dn, "_user_tags", tags, update_modified=False)
			doc = frappe.get_lazy_doc(self.dt, dn)
			update_tags(doc, tags)
			log_tag_changes(doc, old_tags, new_tags)
		except Exception as e:
			if frappe.db.is_missing_column(e):
				if not tags:
					# no tags, nothing to do
					return

				self.setup()
				self.update(dn, tl)
			else:
				raise

	def setup(self):
		"""Add the `_user_tags` column if not exists."""
		from frappe.database.schema import add_column

		add_column(self.dt, "_user_tags", "Data")


def log_tag_changes(doc: Document, old_tags: set[str], new_tags: set[str]) -> None:
	"""Create timeline entries for each tag membership change."""
	for action, tags in ((_("added"), new_tags - old_tags), (_("removed"), old_tags - new_tags)):
		for tag in sorted(tags):
			doc.add_comment("Label", _("{0} tag {1}").format(action, frappe.bold(tag)))


def delete_tags_for_document(doc):
	"""Delete the Tag Link entry of a document that has been deleted.

	:param doc: Deleted document
	"""
	if not frappe.db.table_exists("Tag Link"):
		return

	frappe.db.delete("Tag Link", {"document_type": doc.doctype, "document_name": doc.name})


def update_tags(doc, tags):
	"""Add tags for documents.

	:param doc: Document to be added to global tags
	"""
	doc.check_permission("write")
	new_tags = {tag.strip() for tag in tags.split(",") if tag}
	existing_tags = [
		tag.tag
		for tag in frappe.get_list(
			"Tag Link", filters={"document_type": doc.doctype, "document_name": doc.name}, fields=["tag"]
		)
	]

	added_tags = set(new_tags) - set(existing_tags)
	for tag in added_tags:
		frappe.get_doc(
			{
				"doctype": "Tag Link",
				"document_type": doc.doctype,
				"document_name": doc.name,
				"title": doc.get_title() or "",
				"tag": tag,
			}
		).insert(ignore_permissions=True)

	deleted_tags = list(set(existing_tags) - set(new_tags))
	for tag in deleted_tags:
		frappe.db.delete("Tag Link", {"document_type": doc.doctype, "document_name": doc.name, "tag": tag})


@frappe.whitelist()
def get_documents_for_tag(tag: str):
	"""Search for given text in Tag Link.

	:param tag: tag to be searched
	"""
	# remove hastag `#` from tag
	tag = tag[1:]

	result = frappe.get_list(
		"Tag Link", filters={"tag": tag}, fields=["document_type", "document_name", "title", "tag"]
	)

	return [
		{
			"doctype": res.document_type,
			"name": res.document_name,
			"content": res.title,
		}
		for res in result
	]


@frappe.whitelist()
def get_tags_list_for_awesomebar():
	return [tag["name"] for tag in get_tags_for_app("frappe")]
