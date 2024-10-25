# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.query_builder import DocType
from frappe.utils import unique


class Tag(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
	# end: auto-generated types

	pass


def check_user_tags(dt) -> None:
	"if the user does not have a tags column, then it creates one"
	try:
		doctype = DocType(dt)
		frappe.qb.from_(doctype).select(doctype._user_tags).limit(1).run()
	except Exception as e:
		if frappe.db.is_missing_column(e):
			DocTags(dt).setup()


@frappe.whitelist()
def add_tag(tag, dt, dn, color=None):
	"adds a new tag to a record, and creates the Tag master"
	DocTags(dt).add(dn, tag)

	return tag


@frappe.whitelist()
def add_tags(tags, dt, docs, color=None) -> None:
	"adds a new tag to a record, and creates the Tag master"
	tags = frappe.parse_json(tags)
	docs = frappe.parse_json(docs)
	for doc in docs:
		for tag in tags:
			DocTags(dt).add(doc, tag)


@frappe.whitelist()
def remove_tag(tag, dt, dn) -> None:
	"removes tag from the record"
	DocTags(dt).remove(dn, tag)


@frappe.whitelist()
def get_tagged_docs(doctype, tag):
	frappe.has_permission(doctype, throw=True)
	doctype = DocType(doctype)
	return (frappe.qb.from_(doctype).where(doctype._user_tags.like(tag)).select(doctype.name)).run()


@frappe.whitelist()
def get_tags(doctype, txt):
	tag = frappe.get_list("Tag", filters=[["name", "like", f"%{txt}%"]])
	tags = [t.name for t in tag]

	return sorted(filter(lambda t: t and txt.casefold() in t.casefold(), list(set(tags))))


class DocTags:
	"""Tags for a particular doctype"""

	def __init__(self, dt) -> None:
		self.dt = dt

	def get_tag_fields(self):
		"""Return `tag_fields` property."""
		return frappe.db.get_value("DocType", self.dt, "tag_fields")

	def get_tags(self, dn):
		"""Return tag for a particular item."""
		return (frappe.db.get_value(self.dt, dn, "_user_tags", ignore=1) or "").strip()

	def add(self, dn, tag) -> None:
		"""Add a new user tag."""
		tl = self.get_tags(dn).split(",")
		if tag not in tl:
			tl.append(tag)
			if not frappe.db.exists("Tag", tag):
				frappe.get_doc({"doctype": "Tag", "name": tag}).insert(ignore_permissions=True)
			self.update(dn, tl)

	def remove(self, dn, tag) -> None:
		"""Remove a user tag."""
		tl = self.get_tags(dn).split(",")
		self.update(dn, filter(lambda x: x.lower() != tag.lower(), tl))

	def remove_all(self, dn) -> None:
		"""Remove all user tags (call before delete)."""
		self.update(dn, [])

	def update(self, dn, tl):
		"""Update the `_user_tag` column in the table."""

		if not tl:
			tags = ""
		else:
			tl = unique(filter(lambda x: x, tl))
			tags = ",".join(tl)
		try:
			frappe.db.sql(
				"update `tab{}` set _user_tags={} where name={}".format(self.dt, "%s", "%s"), (tags, dn)
			)
			doc = frappe.get_doc(self.dt, dn)
			update_tags(doc, tags)
		except Exception as e:
			if frappe.db.is_missing_column(e):
				if not tags:
					# no tags, nothing to do
					return

				self.setup()
				self.update(dn, tl)
			else:
				raise

	def setup(self) -> None:
		"""Add the `_user_tags` column if not exists."""
		from frappe.database.schema import add_column

		add_column(self.dt, "_user_tags", "Data")


def delete_tags_for_document(doc) -> None:
	"""Delete the Tag Link entry of a document that has been deleted.

	:param doc: Deleted document
	"""
	if not frappe.db.table_exists("Tag Link"):
		return

	frappe.db.delete("Tag Link", {"document_type": doc.doctype, "document_name": doc.name})


def update_tags(doc, tags) -> None:
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
def get_documents_for_tag(tag):
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
	return frappe.get_list("Tag", pluck="name", order_by=None)
