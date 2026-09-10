# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.desk.query_report import get_print_format_data
from frappe.tests import IntegrationTestCase
from frappe.utils.print_format import render_report_jinja

REPORT = "Test Jinja Print Report"
OTHER_REPORT = "Test Jinja Print Other Report"
PF_JINJA = "Test Jinja Print Format"
PF_JS = "Test Jinja Print JS Format"
PF_DISABLED = "Test Jinja Print Disabled Format"
PF_FOREIGN = "Test Jinja Print Foreign Format"
LETTER_HEAD = "Test Jinja Print Letter Head"
DOCTYPE_LETTER_HEAD = "Test Jinja Print Doctype Letter Head"
NO_ACCESS_USER = "test-jinja-print-no-access@example.com"

TEMPLATE = """
<h1 class="title">{{ report.report_name }}</h1>
<p class="status">{{ filters.status }}</p>
<p class="colcount">{{ columns | length }}</p>
<table>
{% for row in data %}<tr><td>{{ row.subject }}</td></tr>{% endfor %}
</table>
"""

ROWS = [{"subject": "first todo", "status": "Open"}, {"subject": "second todo", "status": "Closed"}]
COLUMNS = [{"fieldname": "subject", "label": "Subject"}, {"fieldname": "status", "label": "Status"}]
FILTERS = {"status": "Open"}


class TestRenderReportJinja(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		make_fixtures()

	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def render(self, **kwargs):
		args = {
			"report_name": REPORT,
			"data": ROWS,
			"columns": COLUMNS,
			"filters": FILTERS,
			"print_format": PF_JINJA,
			"no_letterhead": 1,
		}
		args.update(kwargs)
		return render_report_jinja(**args)

	def test_renders_report_with_client_supplied_data(self):
		body = self.render()["body"]

		self.assertTrue(body.startswith("<style>.title { color: red; }</style>"))
		self.assertIn(REPORT, body)
		self.assertIn("first todo", body)
		self.assertIn("second todo", body)
		self.assertIn(">Open<", body)
		self.assertIn(">2<", body)

	def test_rejects_a_format_that_is_not_this_reports_jinja_format(self):
		for label, print_format in (
			("no format", None),
			("unknown format", "No Such Print Format"),
			("js format", PF_JS),
			("another report's format", PF_FOREIGN),
			("disabled format", PF_DISABLED),
		):
			with self.subTest(label), self.assertRaises(frappe.ValidationError):
				self.render(print_format=print_format)

	def test_letterhead_follows_the_no_letterhead_flag(self):
		self.assertIsNone(self.render(no_letterhead=1)["letter_head"])

		rendered = self.render(no_letterhead=0, letterhead=LETTER_HEAD)
		self.assertIn("Test Jinja Letterhead", rendered["letter_head"]["header"])

	def test_default_letterhead_is_scoped_to_report_flavour(self):
		"""Without a named letterhead the Report default applies, not the DocType one."""
		header = self.render(no_letterhead=0, letterhead=None)["letter_head"]["header"]

		self.assertIn("Test Jinja Letterhead", header)
		self.assertNotIn("Doctype Letterhead", header)

	def test_requires_access_to_the_report(self):
		make_user_without_access()
		frappe.set_user(NO_ACCESS_USER)

		with self.assertRaises(frappe.PermissionError):
			self.render()

	def test_requires_print_permission_on_ref_doctype(self):
		real_has_permission = frappe.has_permission

		def deny_print(doctype=None, ptype="read", *args, **kwargs):
			if ptype == "print":
				return False
			return real_has_permission(doctype, ptype, *args, **kwargs)

		with patch.object(frappe, "has_permission", side_effect=deny_print):
			with self.assertRaises(frappe.PermissionError):
				self.render()


class TestGetPrintFormatData(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		make_fixtures()

	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def test_reports_the_print_format_type(self):
		"""The client picks the jinja vs js flow off this field."""
		self.assertEqual(get_print_format_data(PF_JINJA)["print_format_type"], "Jinja")
		self.assertEqual(get_print_format_data(PF_JS)["print_format_type"], "JS")


def make_fixtures():
	make_report(REPORT)
	make_report(OTHER_REPORT)
	make_print_format(PF_JINJA, REPORT, "Jinja", css=".title { color: red; }")
	make_print_format(PF_JS, REPORT, "JS")
	make_print_format(PF_FOREIGN, OTHER_REPORT, "Jinja")
	make_print_format(PF_DISABLED, REPORT, "Jinja", disabled=1)
	make_letter_head(LETTER_HEAD, "Report", "<div>Test Jinja Letterhead</div>")
	make_letter_head(DOCTYPE_LETTER_HEAD, "DocType", "<div>Doctype Letterhead</div>")


def make_report(name):
	report = frappe.new_doc("Report")
	report.report_name = name
	# Role is not readable by a user with no roles, so the permission gate is testable
	report.ref_doctype = "Role"
	report.report_type = "Query Report"
	report.is_standard = "No"
	report.query = "select name from `tabRole` limit 1"
	report.insert(ignore_permissions=True, ignore_if_duplicate=True)


def make_print_format(name, report, print_format_type, css="", disabled=0):
	pf = frappe.new_doc("Print Format")
	pf.name = name
	pf.print_format_for = "Report"
	pf.report = report
	pf.print_format_type = print_format_type
	pf.standard = "No"
	pf.custom_format = 1
	pf.html = TEMPLATE
	pf.css = css
	pf.insert(ignore_permissions=True, ignore_if_duplicate=True)
	if disabled:
		# set after insert so the format passes its own validation first
		frappe.db.set_value("Print Format", name, "disabled", 1)


def make_letter_head(name, letter_head_for, content):
	lh = frappe.new_doc("Letter Head")
	lh.letter_head_name = name
	lh.letter_head_for = letter_head_for
	lh.source = "HTML"
	lh.content = content
	lh.is_default = 1
	lh.insert(ignore_permissions=True, ignore_if_duplicate=True)


def make_user_without_access():
	user = frappe.new_doc("User")
	user.email = NO_ACCESS_USER
	user.first_name = "No Access"
	user.send_welcome_email = 0
	user.insert(ignore_permissions=True, ignore_if_duplicate=True)
