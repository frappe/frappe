# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.dashboard_renderer import (
	INSIGHTS,
	INSIGHTS_APP,
	INSIGHTS_DASHBOARD_DOCTYPE,
	LEGACY,
	SETTINGS_FIELD,
	get_dashboard_renderer,
	get_insights_rendered_doctype,
	get_renderer_for_reference,
)

# The one path framework takes into Insights. Named here so a move on the Insights
# side fails this suite rather than a desk route.
INSIGHTS_RESOLVER = "insights.resolver.resolve"


@contextmanager
def site(*, installed: bool, flag: bool, resolves: tuple[str, ...] = ()):
	# The setting is patched, not saved, so a case costs no write. One test below
	# goes through the real field. Every other setting keeps its real value, or the
	# framework reads a timezone of `1` and breaks.
	#
	# `resolves` names the references Insights answers for. Insights' own resolver is
	# patched in, so this suite runs on a bench that does not have Insights at all.
	apps = ["frappe", INSIGHTS_APP] if installed else ["frappe"]
	real_get_system_settings = frappe.get_system_settings
	real_get_attr = frappe.get_attr

	def get_system_settings(field):
		if field == SETTINGS_FIELD:
			return 1 if flag else 0
		return real_get_system_settings(field)

	def get_attr(method_string):
		if method_string == INSIGHTS_RESOLVER:
			return lambda doctype, reference: reference if reference in resolves else None
		return real_get_attr(method_string)

	with (
		patch.object(frappe, "get_installed_apps", return_value=apps),
		patch.object(frappe, "get_system_settings", side_effect=get_system_settings),
		patch.object(frappe, "get_attr", side_effect=get_attr),
	):
		yield


class TestDashboardRenderer(IntegrationTestCase):
	def test_condition_table(self):
		# Insights renders a dashboard only when all three conditions hold.
		cases = {
			(INSIGHTS_DASHBOARD_DOCTYPE, True, True): INSIGHTS,
			(INSIGHTS_DASHBOARD_DOCTYPE, True, False): LEGACY,
			(INSIGHTS_DASHBOARD_DOCTYPE, False, True): LEGACY,
			(INSIGHTS_DASHBOARD_DOCTYPE, False, False): LEGACY,
			("Dashboard", True, True): LEGACY,
			("Dashboard", True, False): LEGACY,
			("Dashboard", False, True): LEGACY,
			("Dashboard", False, False): LEGACY,
		}

		for (doctype, installed, flag), expected in cases.items():
			with (
				self.subTest(doctype=doctype, installed=installed, flag=flag),
				site(installed=installed, flag=flag),
			):
				self.assertEqual(get_dashboard_renderer(doctype), expected)

	def test_the_setting_reads_the_real_system_settings_field(self):
		# The only case that touches the field itself, so that a renamed or missing
		# field fails here rather than passing on a patched value.
		with patch.object(frappe, "get_installed_apps", return_value=["frappe", INSIGHTS_APP]):
			with self.change_settings("System Settings", {SETTINGS_FIELD: 1}):
				self.assertEqual(get_dashboard_renderer(INSIGHTS_DASHBOARD_DOCTYPE), INSIGHTS)

			with self.change_settings("System Settings", {SETTINGS_FIELD: 0}):
				self.assertEqual(get_dashboard_renderer(INSIGHTS_DASHBOARD_DOCTYPE), LEGACY)

	def test_the_setting_is_off_when_the_site_never_set_it(self):
		with (
			patch.object(frappe, "get_installed_apps", return_value=["frappe", INSIGHTS_APP]),
			patch.object(frappe, "get_system_settings", return_value=None),
		):
			self.assertEqual(get_dashboard_renderer(INSIGHTS_DASHBOARD_DOCTYPE), LEGACY)

	def test_an_unrelated_doctype_gets_the_legacy_renderer(self):
		with site(installed=True, flag=True):
			self.assertEqual(get_dashboard_renderer("Workspace"), LEGACY)
			self.assertEqual(get_dashboard_renderer(""), LEGACY)

	def test_a_legacy_dashboard_keeps_a_reference_insights_does_not_resolve(self):
		# Only the name is looked up, so the dashboard needs no charts.
		dashboard = frappe.get_doc(doctype="Dashboard", dashboard_name=frappe.generate_hash()).insert(
			ignore_mandatory=True
		)
		with site(installed=True, flag=True):
			self.assertEqual(get_renderer_for_reference(dashboard.name), LEGACY)

	def test_insights_wins_a_name_a_legacy_dashboard_also_carries(self):
		# The collision that moves a route. The legacy document stays where it is, and
		# the route it used to draw now comes from Insights.
		dashboard = frappe.get_doc(doctype="Dashboard", dashboard_name=frappe.generate_hash()).insert(
			ignore_mandatory=True
		)
		with site(installed=True, flag=True, resolves=(dashboard.name,)):
			self.assertEqual(get_renderer_for_reference(dashboard.name), INSIGHTS)

	def test_insights_is_asked_for_the_dashboard_doctype_and_the_raw_reference(self):
		# Framework hands the reference over untouched — Insights owns every form it
		# accepts, and framework knows none of them.
		asked = []

		def resolve(doctype, reference):
			asked.append((doctype, reference))
			return None

		with (
			site(installed=True, flag=True),
			patch.object(frappe, "get_attr", return_value=resolve),
		):
			get_renderer_for_reference("insights/selling")

		self.assertEqual(asked, [(INSIGHTS_DASHBOARD_DOCTYPE, "insights/selling")])

	def test_any_other_reference_goes_to_insights_unresolved(self):
		# Nothing here resolves and no legacy `Dashboard` carries these names, so they
		# all answer Insights, which draws the nothing-there state.
		with site(installed=True, flag=True):
			for reference in ("sales-performance", "insights/sales-performance", "no-such-thing"):
				with self.subTest(reference=reference):
					self.assertEqual(get_renderer_for_reference(reference), INSIGHTS)

	def test_the_bare_route_gets_the_legacy_renderer(self):
		# `/app/dashboard-view` names no dashboard. The legacy flow picks one.
		with site(installed=True, flag=True):
			self.assertEqual(get_renderer_for_reference(""), LEGACY)

	def test_a_reference_gets_the_legacy_renderer_while_the_flag_is_off(self):
		for installed, flag in ((True, False), (False, True), (False, False)):
			with self.subTest(installed=installed, flag=flag), site(installed=installed, flag=flag):
				self.assertEqual(get_renderer_for_reference("sales-performance"), LEGACY)

	def test_boot_names_the_doctype_insights_renders(self):
		with site(installed=True, flag=True):
			self.assertEqual(get_insights_rendered_doctype(), INSIGHTS_DASHBOARD_DOCTYPE)

	def test_boot_carries_nothing_while_the_flag_is_off(self):
		for installed, flag in ((True, False), (False, True), (False, False)):
			with self.subTest(installed=installed, flag=flag), site(installed=installed, flag=flag):
				self.assertIsNone(get_insights_rendered_doctype())

	def test_the_flag_reaches_the_browser_through_boot(self):
		# The client answers from this field alone while the flag is off, so boot
		# must carry it. It must sit outside the boot cache, so that a change to
		# the flag takes effect.
		frappe.local.request = None
		self.addCleanup(lambda: delattr(frappe.local, "request"))

		with site(installed=True, flag=True):
			self.assertEqual(frappe.sessions.get().insights_rendered_doctype, INSIGHTS_DASHBOARD_DOCTYPE)

		with site(installed=True, flag=False):
			self.assertIsNone(frappe.sessions.get().insights_rendered_doctype)
