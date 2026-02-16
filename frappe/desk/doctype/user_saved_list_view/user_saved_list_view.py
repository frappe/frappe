# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class UserSavedListView(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		allow_edit: DF.Check
		columns: DF.Code | None
		disable_auto_refresh: DF.Check
		disable_automatic_recency_filters: DF.Check
		disable_comment_count: DF.Check
		disable_count: DF.Check
		disable_scrolling: DF.Check
		disable_sidebar_stats: DF.Check
		filters: DF.Code | None
		is_public: DF.Check
		reference_doctype: DF.Link
		show_tags: DF.Check
		sort_by: DF.Data | None
		sort_order: DF.Literal["asc", "desc"]
		view_name: DF.Data
	# end: auto-generated types

	def before_insert(self):
		# Set the owner to current user if not set
		if not self.owner:
			self.owner = frappe.session.user

	def validate(self):
		# Only System Manager can create public views
		if self.is_public and "System Manager" not in frappe.get_roles():
			frappe.throw(_("Only System Manager can create public views"))

		# Check if user has permission to the reference doctype
		if not frappe.has_permission(self.reference_doctype, "read"):
			frappe.throw(_("You don't have permission to access {0}").format(self.reference_doctype))

		# Check for duplicate view names for this doctype and user
		existing = frappe.db.exists(
			"User Saved List View",
			{
				"view_name": self.view_name,
				"reference_doctype": self.reference_doctype,
				"owner": self.owner,
				"name": ("!=", self.name or ""),
			},
		)
		if existing:
			frappe.throw(_("A view with name '{0}' already exists for {1}").format(self.view_name, self.reference_doctype))

	def has_permission(self, ptype, user=None):
		"""Custom permission check for User Saved List View"""
		user = user or frappe.session.user
		
		# System Manager can do anything
		if "System Manager" in frappe.get_roles(user):
			return True

		# For read permission, allow if view is public or owned by user
		if ptype == "read":
			return self.is_public or self.owner == user

		# For write/delete, only allow if owner
		return self.owner == user


@frappe.whitelist()
def get_views(doctype):
	"""Get all available views for a doctype (user's private views + public views)"""
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("You don't have permission to access {0}").format(doctype))

	# Get user's private views
	private_views = frappe.get_all(
		"User Saved List View",
		filters={
			"reference_doctype": doctype,
			"owner": frappe.session.user,
			"is_public": 0,
		},
		fields=["name", "view_name", "is_public", "owner"],
		order_by="view_name asc",
	)

	# Get public views
	public_views = frappe.get_all(
		"User Saved List View",
		filters={
			"reference_doctype": doctype,
			"is_public": 1,
		},
		fields=["name", "view_name", "is_public", "owner"],
		order_by="view_name asc",
	)

	return {
		"private": private_views,
		"public": public_views,
	}


@frappe.whitelist()
def get_view(name):
	"""Get a specific view by name"""
	doc = frappe.get_doc("User Saved List View", name)
	
	# Check permission
	if not doc.has_permission("read"):
		frappe.throw(_("You don't have permission to access this view"))

	return doc.as_dict()


@frappe.whitelist()
def save_view(doctype, view_name, columns, filters, sort_by, sort_order, settings, is_public=0, view_id=None):
	"""Save or update a view"""
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("You don't have permission to access {0}").format(doctype))

	settings = frappe.parse_json(settings) if settings else {}

	if view_id:
		# Update existing view
		doc = frappe.get_doc("User Saved List View", view_id)
		if not doc.has_permission("write"):
			frappe.throw(_("You don't have permission to edit this view"))
	else:
		# Create new view
		doc = frappe.new_doc("User Saved List View")
		doc.reference_doctype = doctype
		doc.owner = frappe.session.user

	doc.view_name = view_name
	doc.columns = columns
	doc.filters = filters
	doc.sort_by = sort_by
	doc.sort_order = (sort_order or "desc").lower()
	doc.is_public = int(is_public)

	# Apply settings
	doc.disable_count = settings.get("disable_count", 0)
	doc.disable_auto_refresh = settings.get("disable_auto_refresh", 0)
	doc.disable_sidebar_stats = settings.get("disable_sidebar_stats", 0)
	doc.disable_automatic_recency_filters = settings.get("disable_automatic_recency_filters", 0)
	doc.disable_comment_count = settings.get("disable_comment_count", 0)
	doc.disable_scrolling = settings.get("disable_scrolling", 0)
	doc.allow_edit = settings.get("allow_edit", 0)
	doc.show_tags = settings.get("show_tags", 0)

	doc.save()
	frappe.db.commit()

	return {"name": doc.name, "view_name": doc.view_name}


@frappe.whitelist()
def delete_view(name):
	"""Delete a view"""
	doc = frappe.get_doc("User Saved List View", name)
	
	if not doc.has_permission("delete"):
		frappe.throw(_("You don't have permission to delete this view"))

	doc.delete()
	frappe.db.commit()

	return {"success": True}


@frappe.whitelist()
def set_default_view(doctype, view_name=None):
	"""Set a view as default for the current user"""
	from frappe.model.utils.user_settings import update_user_settings

	update_user_settings(doctype, {"default_list_view": view_name})
	return {"success": True}


@frappe.whitelist()
def get_default_view(doctype):
	"""Get the default view for the current user"""
	import json

	from frappe.model.utils.user_settings import get_user_settings

	settings = json.loads(get_user_settings(doctype) or "{}")
	return settings.get("default_list_view")
