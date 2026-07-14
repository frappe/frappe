# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from functools import cached_property

import frappe
from frappe.permissions import has_permission
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count
from frappe.query_builder.terms import SubQuery
from frappe.utils.data import cstr


class DeskViews:
	"""Builds the desk views (workspaces, dashboards, pages and reports) for the boot payload."""

	# allowed-entity caches refresh every six hours
	CACHE_EXPIRY = 6 * 60 * 60

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
		self.dashboards = self.get_allowed_dashboards(cache=True)
		return self

	def add_to_boot(self, bootinfo):
		bootinfo.page_info = self.pages
		bootinfo.allowed_reports = self.reports
		bootinfo.workspaces = self.workspaces
		bootinfo.dashboards = self.dashboards

	# The properties below are the per-user view-permission data read by `is_item_allowed`.
	# They load lazily and cache on the instance, so consumers don't need to populate them.

	@cached_property
	def allowed_pages(self):
		return self.get_allowed_pages(cache=True)

	@cached_property
	def allowed_reports(self):
		return self.get_allowed_reports(cache=True)

	@cached_property
	def allowed_dashboards(self):
		return {d["name"] for d in self.get_allowed_dashboards(cache=True)}

	@cached_property
	def restricted_doctypes(self):
		from frappe.cache_manager import build_domain_restricted_doctype_cache

		return frappe.cache.get_value("domain_restricted_doctypes") or build_domain_restricted_doctype_cache()

	@cached_property
	def restricted_pages(self):
		from frappe.cache_manager import build_domain_restricted_page_cache

		return frappe.cache.get_value("domain_restricted_pages") or build_domain_restricted_page_cache()

	@cached_property
	def can_read(self):
		"""Doctypes the session user may read. Built lazily so subclasses used purely as a
		permission context don't pay for it on construction."""
		user = frappe.get_user()
		if not user.can_read:
			user.build_permissions()
		return user.can_read

	@cached_property
	def allowed_workspaces(self):
		"""Names of the workspaces the session user may see. Built lazily, like the other
		permission caches above."""
		from frappe.desk.desktop import get_workspaces

		return [page.name for page in get_workspaces()["pages"]]

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
	def get_allowed_dashboards(cls, cache=False):
		"""Return dashboards the user is allowed to see.

		A dashboard is permitted when the user can access at least one of its charts or cards.
		Evaluated for the current session user and cached like pages and reports.
		"""
		from frappe.desk.doctype.dashboard.dashboard import get_permitted_cards, get_permitted_charts

		def build():
			return [
				{"name": name}
				for name in frappe.get_all("Dashboard", pluck="name")
				if get_permitted_charts(name) or get_permitted_cards(name)
			]

		return cls._allowed_entity_cache("allowed_dashboards", frappe.session.user, build, cache=cache)

	@classmethod
	def _allowed_entity_cache(cls, key, user, builder, cache=False):
		"""Return the user's allowed entities for `key`, rebuilding and re-caching on a miss.

		Pass `cache=True` to return a previously cached value instead of rebuilding. The result
		is stored per-user and expires after `CACHE_EXPIRY` seconds.
		"""
		if cache:
			cached = frappe.cache.get_value(key, user=user)
			if cached:
				return cached

		value = builder()
		frappe.cache.set_value(key, value, user, cls.CACHE_EXPIRY)
		return value

	@classmethod
	def get_user_pages_or_reports(cls, parent, cache=False, user: str | None = None):
		if user is None:
			user = frappe.session.user

		return cls._allowed_entity_cache(
			"has_role:" + parent,
			user,
			lambda: cls._build_user_pages_or_reports(parent, user),
			cache=cache,
		)

	@classmethod
	def _build_user_pages_or_reports(cls, parent, user):
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

		return has_role
