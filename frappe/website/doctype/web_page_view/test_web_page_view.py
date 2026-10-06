# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

import frappe
from frappe.deferred_insert import save_to_db
from frappe.tests import IntegrationTestCase
from frappe.utils import get_url
from frappe.utils.logging import ensure_log_table, get_log_db, is_log_doctype
from frappe.website.doctype.web_page_view.web_page_view import (
	WebPageView,
	get_page_view_count,
	make_view_log,
)
from frappe.website.report.website_analytics.website_analytics import execute as website_analytics


class TestWebPageView(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		ensure_log_table("Web Page View")
		self.log_db = get_log_db()
		self._clear_views()
		self.addCleanup(self._clear_views)
		self.addCleanup(get_page_view_count.clear_cache)

	def _clear_views(self):
		self.log_db.sql("DELETE FROM `tabWeb Page View`")
		self.log_db.commit()

	def _add_view(self, creation=None, **kwargs):
		"""Record a view, optionally backdated.

		`creation` cannot be handed to `insert`: `set_user_and_timestamp` overwrites it for
		every new document outside an install or a patch. Backdating afterwards keeps the
		insert itself on the same path a real view takes.
		"""
		view = frappe.get_doc(doctype="Web Page View", **kwargs).insert(ignore_permissions=True)

		if creation:
			self.log_db.sql(
				"UPDATE `tabWeb Page View` SET creation = %(creation)s WHERE name = %(name)s",
				{"creation": creation, "name": view.name},
			)
			self.log_db.commit()

		return view

	def test_views_are_stored_in_the_log_database(self):
		self.assertTrue(is_log_doctype("Web Page View"))
		self.assertTrue(frappe.get_meta("Web Page View").is_virtual)

		view = self._add_view(path="pricing", visitor_id="v1", is_unique=True)

		self.assertEqual(self.log_db.get_value("Web Page View", view.name, "path"), "pricing")
		self.assertEqual(self.log_db.count("Web Page View"), 1)

	def test_document_roundtrip_through_the_log_database(self):
		view = self._add_view(path="pricing", browser="chrome")

		reloaded = frappe.get_doc("Web Page View", view.name)
		self.assertEqual(reloaded.path, "pricing")

		reloaded.db_set("browser", "firefox", update_modified=False)
		self.assertEqual(self.log_db.get_value("Web Page View", view.name, "browser"), "firefox")

		reloaded.delete()
		self.assertFalse(self.log_db.exists("Web Page View", view.name))

	def test_list_view_reads_the_log_database(self):
		self._add_view(path="pricing")
		self._add_view(path="about")

		paths = {d.path for d in frappe.get_all("Web Page View", fields=["path"])}
		self.assertEqual(paths, {"pricing", "about"})

		self.assertEqual(len(frappe.get_all("Web Page View", pluck="name")), 2)
		self.assertEqual(len(frappe.get_all("Web Page View", filters={"path": "about"})), 1)
		self.assertEqual(WebPageView.get_count("Web Page View"), 2)

	def test_page_view_count(self):
		self._add_view(path="pricing")
		self._add_view(path="pricing")
		self._add_view(path="about")

		get_page_view_count.clear_cache()
		self.assertEqual(get_page_view_count("pricing"), 2)

	def test_clear_old_logs(self):
		self._add_view(path="stale", creation="2020-01-01 00:00:00.000000")
		self._add_view(path="fresh")

		WebPageView.clear_old_logs(days=30)

		self.assertEqual(frappe.get_all("Web Page View", pluck="path"), ["fresh"])

	def test_make_view_log_tracks_a_visitor_once(self):
		builder = EnvironBuilder(
			base_url=get_url(),
			headers={"Referer": get_url("/contact?utm=x"), "User-Agent": "test-agent"},
		)
		previous_request = getattr(frappe.local, "request", None)
		self.addCleanup(setattr, frappe.local, "request", previous_request)
		frappe.local.request = Request(builder.get_environ())

		with self.change_settings("Website Settings", enable_view_tracking=1):
			# `make_view_log` queues the row rather than inserting it, and decides `is_unique`
			# from what is already stored -- so the queue has to be drained between the two
			# views for the second one to see the first, exactly as it is between two requests.
			for _ in range(2):
				make_view_log(referrer="https://example.com/post?utm=x", browser="chrome", visitor_id="v1")
				save_to_db(doctype="Web Page View")

		views = frappe.get_all(
			"Web Page View",
			fields=["path", "referrer", "user_agent", "is_unique"],
			order_by="creation asc",
		)

		self.assertEqual([v.path for v in views], ["contact", "contact"])
		self.assertEqual(views[0].referrer, "https://example.com/post")
		self.assertEqual(views[0].user_agent, "test-agent")
		# The uniqueness check has to find the first view, which only the log database holds.
		self.assertEqual([v.is_unique for v in views], ["1", "0"])

	def test_analytics_report_groups_and_charts_log_rows(self):
		# A Tuesday and a Wednesday in the same week, then one the week after.
		self._add_view(path="pricing", is_unique=True, creation="2026-09-01 10:00:00.000000")
		self._add_view(path="pricing", is_unique=False, creation="2026-09-02 10:00:00.000000")
		self._add_view(path="about", is_unique=True, creation="2026-09-08 10:00:00.000000")

		filters = {"from_date": "2026-08-25", "to_date": "2026-09-10", "group_by": "path"}

		_, data, _, _, summary = website_analytics({**filters, "range": "Daily"})

		self.assertEqual(data, [("pricing", 2, 1), ("about", 1, 1)])
		self.assertEqual([s["value"] for s in summary], [3, 2])

		# Every bucket the chart produces has to land on one of the labels it is plotted
		# against, or the series reads as a flat zero line.
		for time_range in ("Daily", "Weekly", "Monthly"):
			with self.subTest(range=time_range):
				_, _, _, chart, _ = website_analytics({**filters, "range": time_range})
				totals, unique = (dataset["values"] for dataset in chart["data"]["datasets"])

				self.assertEqual(sum(totals), 3)
				self.assertEqual(sum(unique), 2)
