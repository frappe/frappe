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

		# A view is committed to the log database as it is written, so it outlives the test
		# transaction: clearing the table would take a real site's page views with it. Every
		# row this test creates is recorded and removed by name instead, and paths are
		# prefixed per test so the reads cannot pick up views that were already there.
		self.prefix = f"_test-{frappe.generate_hash(length=10)}"
		self.view_names = []

		self.addCleanup(self._remove_own_views)
		self.addCleanup(get_page_view_count.clear_cache)

	def _remove_own_views(self):
		if self.view_names:
			self.log_db.delete("Web Page View", {"name": ("in", self.view_names)})
			self.log_db.commit()

	def _path(self, path):
		"""Namespace a path to this test, so a real site's views cannot be mistaken for it."""
		return f"{self.prefix}/{path}"

	def _visitor(self, visitor_id):
		"""Namespace a visitor id, for the same reason as `_path`."""
		return f"{self.prefix}/{visitor_id}"

	def _own_views(self):
		"""Filters matching only the views this test created."""
		return {"name": ("in", self.view_names or [""])}

	def _add_view(self, creation=None, **kwargs):
		"""Record a view, optionally backdated.

		`creation` cannot be handed to `insert`: `set_user_and_timestamp` overwrites it for
		every new document outside an install or a patch. Backdating afterwards keeps the
		insert itself on the same path a real view takes.
		"""
		view = frappe.get_doc(doctype="Web Page View", **kwargs).insert(ignore_permissions=True)
		self.view_names.append(view.name)

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

		view = self._add_view(path=self._path("pricing"), visitor_id=self._visitor("v1"), is_unique=True)

		self.assertEqual(self.log_db.get_value("Web Page View", view.name, "path"), self._path("pricing"))
		self.assertEqual(self.log_db.count("Web Page View", self._own_views()), 1)

	def test_document_roundtrip_through_the_log_database(self):
		view = self._add_view(path=self._path("pricing"), browser="chrome")

		reloaded = frappe.get_doc("Web Page View", view.name)
		self.assertEqual(reloaded.path, self._path("pricing"))

		reloaded.db_set("browser", "firefox", update_modified=False)
		self.assertEqual(self.log_db.get_value("Web Page View", view.name, "browser"), "firefox")

		reloaded.delete()
		self.assertFalse(self.log_db.exists("Web Page View", view.name))

	def test_get_doc_accepts_filters_instead_of_a_name(self):
		"""`frappe.get_doc(doctype, <dict>)` has to work, as it does for any other DocType.

		`Document.load_from_db` treats a non-scalar `name` as a set of filters, and callers
		lean on it to turn a row from `frappe.get_all` straight into a document. Comparing
		the `name` column against a dict renders the dict into the SQL instead.
		"""
		view = self._add_view(path=self._path("pricing"), visitor_id=self._visitor("v1"))

		row = frappe.get_all("Web Page View", filters={"path": self._path("pricing")})[0]
		self.assertIsInstance(row, dict)
		self.assertEqual(frappe.get_doc("Web Page View", row).name, view.name)

		# a filter on something other than `name` is the same contract
		self.assertEqual(frappe.get_doc("Web Page View", {"visitor_id": self._visitor("v1")}).name, view.name)

		# and a scalar name still takes the direct path
		self.assertEqual(frappe.get_doc("Web Page View", view.name).name, view.name)

		with self.assertRaises(frappe.DoesNotExistError):
			frappe.get_doc("Web Page View", {"visitor_id": self._visitor("no-such-visitor")})

	def test_list_view_reads_the_log_database(self):
		self._add_view(path=self._path("pricing"))
		self._add_view(path=self._path("about"))

		paths = {d.path for d in frappe.get_all("Web Page View", fields=["path"], filters=self._own_views())}
		self.assertEqual(paths, {self._path("pricing"), self._path("about")})

		self.assertEqual(len(frappe.get_all("Web Page View", pluck="name", filters=self._own_views())), 2)
		self.assertEqual(len(frappe.get_all("Web Page View", filters={"path": self._path("about")})), 1)
		self.assertEqual(WebPageView.get_count("Web Page View", self._own_views()), 2)

	def test_page_view_count(self):
		self._add_view(path=self._path("pricing"))
		self._add_view(path=self._path("pricing"))
		self._add_view(path=self._path("about"))

		get_page_view_count.clear_cache()
		self.assertEqual(get_page_view_count(self._path("pricing")), 2)

	def test_clear_old_logs(self):
		self._add_view(path=self._path("stale"), creation="2020-01-01 00:00:00.000000")
		self._add_view(path=self._path("fresh"))

		WebPageView.clear_old_logs(days=30)

		self.assertEqual(
			frappe.get_all("Web Page View", pluck="path", filters=self._own_views()),
			[self._path("fresh")],
		)

	def test_make_view_log_tracks_a_visitor_once(self):
		builder = EnvironBuilder(
			base_url=get_url(),
			headers={"Referer": get_url(f"/{self._path('contact')}?utm=x"), "User-Agent": "test-agent"},
		)
		previous_request = getattr(frappe.local, "request", None)
		self.addCleanup(setattr, frappe.local, "request", previous_request)
		frappe.local.request = Request(builder.get_environ())

		with self.change_settings("Website Settings", enable_view_tracking=1):
			# `make_view_log` queues the row rather than inserting it, and decides `is_unique`
			# from what is already stored -- so the queue has to be drained between the two
			# views for the second one to see the first, exactly as it is between two requests.
			for _ in range(2):
				make_view_log(
					referrer="https://example.com/post?utm=x",
					browser="chrome",
					visitor_id=self._visitor("v1"),
				)
				save_to_db(doctype="Web Page View")

		# `make_view_log` inserts through the deferred queue, so the rows are not created by
		# `_add_view` and have to be collected here for the cleanup to find them.
		views = frappe.get_all(
			"Web Page View",
			fields=["name", "path", "referrer", "user_agent", "is_unique"],
			filters={"path": self._path("contact")},
			order_by="creation asc",
		)
		self.view_names.extend(v.name for v in views)

		self.assertEqual([v.path for v in views], [self._path("contact")] * 2)
		self.assertEqual(views[0].referrer, "https://example.com/post")
		self.assertEqual(views[0].user_agent, "test-agent")
		# The uniqueness check has to find the first view, which only the log database holds.
		self.assertEqual([v.is_unique for v in views], ["1", "0"])

	def test_analytics_report_groups_and_charts_log_rows(self):
		# The report filters on `creation` alone -- it takes no path filter -- so the reporting
		# window is the only thing that can keep a real site's views out of these totals. A
		# window far enough back that nothing else occupies it does that; the rows below are
		# backdated into it anyway, so the dates are free. Weekday shape is what matters: a
		# Tuesday and a Wednesday in the same week, then one the week after.
		self._add_view(path=self._path("pricing"), is_unique=True, creation="1990-01-02 10:00:00.000000")
		self._add_view(path=self._path("pricing"), is_unique=False, creation="1990-01-03 10:00:00.000000")
		self._add_view(path=self._path("about"), is_unique=True, creation="1990-01-09 10:00:00.000000")

		filters = {"from_date": "1989-12-26", "to_date": "1990-01-11", "group_by": "path"}

		_, data, _, _, summary = website_analytics({**filters, "range": "Daily"})

		self.assertEqual(data, [(self._path("pricing"), 2, 1), (self._path("about"), 1, 1)])
		self.assertEqual([s["value"] for s in summary], [3, 2])

		# Every bucket the chart produces has to land on one of the labels it is plotted
		# against, or the series reads as a flat zero line.
		for time_range in ("Daily", "Weekly", "Monthly"):
			with self.subTest(range=time_range):
				_, _, _, chart, _ = website_analytics({**filters, "range": time_range})
				totals, unique = (dataset["values"] for dataset in chart["data"]["datasets"])

				self.assertEqual(sum(totals), 3)
				self.assertEqual(sum(unique), 2)
