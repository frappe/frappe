# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.permissions import has_permission
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count
from frappe.query_builder.terms import SubQuery
from frappe.utils.data import cstr


class DeskEntity:
	"""Builds the desk entities (workspaces, dashboards, pages and reports) for the boot payload."""

	def __init__(self):
		self.pages = {}
		self.reports = {}
		self.workspaces = {}
		self.dashboards = []

	def build_entities(self):
		from frappe.desk.desktop import get_workspaces

		self.pages = self.get_allowed_pages()
		self.reports = self.get_allowed_reports()
		self.workspaces = get_workspaces()
		self.dashboards = frappe.get_all("Dashboard")
		return self

	def add_to_boot(self, bootinfo):
		bootinfo.page_info = self.pages
		bootinfo.allowed_reports = self.reports
		bootinfo.workspaces = self.workspaces
		bootinfo.dashboards = self.dashboards

	@classmethod
	def get_allowed_pages(cls, cache=False, user: str | None = None):
		return cls.get_user_pages_or_reports("Page", cache=cache, user=user)

	@classmethod
	def get_allowed_reports(cls, cache=False, user: str | None = None):
		return cls.get_user_pages_or_reports("Report", cache=cache, user=user)

	@classmethod
	def get_allowed_report_names(cls, cache=False, user: str | None = None) -> set[str]:
		return {cstr(report) for report in cls.get_allowed_reports(cache=cache, user=user).keys() if report}

	@classmethod
	def get_user_pages_or_reports(cls, parent, cache=False, user: str | None = None):
		if user is None:
			user = frappe.session.user

		if cache:
			has_role = frappe.cache.get_value("has_role:" + parent, user=user)
			if has_role:
				return has_role

		roles = frappe.get_roles(user)
		has_role = {}

		page = DocType("Page")
		report = DocType("Report")

		is_report = parent == "Report"

		if is_report:
			columns = (report.name.as_("title"), report.ref_doctype, report.report_type)
		else:
			columns = (page.title.as_("title"),)

		customRole = DocType("Custom Role")
		hasRole = DocType("Has Role")
		parentTable = DocType(parent)

		# get pages or reports set on custom role
		pages_with_custom_roles = (
			frappe.qb.from_(customRole)
			.from_(hasRole)
			.from_(parentTable)
			.select(
				customRole[parent.lower()].as_("name"), customRole.modified, customRole.ref_doctype, *columns
			)
			.where(
				(hasRole.parent == customRole.name)
				& (parentTable.name == customRole[parent.lower()])
				& (customRole[parent.lower()].isnotnull())
				& (hasRole.role.isin(roles))
			)
		).run(as_dict=True)

		for p in pages_with_custom_roles:
			has_role[p.name] = {"modified": p.modified, "title": p.title, "ref_doctype": p.ref_doctype}

		subq = (
			frappe.qb.from_(customRole)
			.select(customRole[parent.lower()])
			.where(customRole[parent.lower()].isnotnull())
		)

		pages_with_standard_roles = (
			frappe.qb.from_(hasRole)
			.from_(parentTable)
			.select(parentTable.name.as_("name"), parentTable.modified, *columns)
			.where(
				(hasRole.role.isin(roles))
				& (hasRole.parent == parentTable.name)
				& (parentTable.name.notin(subq))
			)
			.distinct()
		)

		if is_report:
			pages_with_standard_roles = pages_with_standard_roles.where(report.disabled == 0)

		pages_with_standard_roles = pages_with_standard_roles.run(as_dict=True)

		for p in pages_with_standard_roles:
			if p.name not in has_role:
				has_role[p.name] = {"modified": p.modified, "title": p.title}
				if parent == "Report":
					has_role[p.name].update({"ref_doctype": p.ref_doctype})

		no_of_roles = SubQuery(
			frappe.qb.from_(hasRole).select(Count("*")).where(hasRole.parent == parentTable.name)
		)

		# pages and reports with no role are allowed
		rows_with_no_roles = (
			frappe.qb.from_(parentTable)
			.select(parentTable.name, parentTable.modified, *columns)
			.where(no_of_roles == 0)
		).run(as_dict=True)

		for r in rows_with_no_roles:
			if r.name not in has_role:
				has_role[r.name] = {"modified": r.modified, "title": r.title}
				if is_report:
					has_role[r.name] |= {"ref_doctype": r.ref_doctype}

		if is_report:
			if not has_permission("Report", user=user, print_logs=False):
				return {}

			reports = frappe.get_list(
				"Report",
				fields=["name", "report_type"],
				filters={"name": ("in", has_role.keys())},
				ignore_ifnull=True,
				user=user,
			)
			for report in reports:
				has_role[report.name]["report_type"] = report.report_type

			non_permitted_reports = set(has_role.keys()) - {r.name for r in reports}
			for r in non_permitted_reports:
				has_role.pop(r, None)

		# Expire every six hours
		frappe.cache.set_value("has_role:" + parent, has_role, user, 21600)
		return has_role
