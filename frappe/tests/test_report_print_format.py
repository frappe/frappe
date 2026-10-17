# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.desk.query_report import get_print_format_data, run
from frappe.tests import IntegrationTestCase
from frappe.utils.print_format import download_report_pdf, render_report_jinja

REPORT = "Test Jinja Print Report"
PF_JINJA = "Test Jinja Print Format"
PF_JS = "Test Jinja Print JS Format"
PF_DISABLED = "Test Jinja Print Disabled Format"
PF_TODO = "Test Jinja Print ToDo Format"
LETTER_HEAD = "Test Jinja Print Letter Head"
DOCTYPE_LETTER_HEAD = "Test Jinja Print Doctype Letter Head"
NO_ACCESS_USER = "test-jinja-print-no-access@example.com"
REPORT_USER = "test-jinja-print-report-user@example.com"

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

	def test_rejects_a_format_that_is_not_an_enabled_jinja_report_format(self):
		for label, print_format in (
			("unknown format", "No Such Print Format"),
			("js format", PF_JS),
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


class TestDownloadReportPdf(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		make_fixtures()
		make_print_format(PF_TODO, "ToDo", "Jinja")
		make_report_user()
		frappe.set_user(REPORT_USER)
		for priority, description in (
			("High", "Renew the example.com domain"),
			("Low", "Archive old invoices"),
		):
			frappe.get_doc({"doctype": "ToDo", "priority": priority, "description": description}).insert()
		frappe.set_user("Administrator")

	def setUp(self):
		frappe.set_user(REPORT_USER)
		self.addCleanup(frappe.set_user, "Administrator")

	def printed_html(self, **kwargs):
		with patch("frappe.utils.print_format.get_pdf", return_value=b"%PDF") as get_pdf:
			download_report_pdf("ToDo", no_letterhead=1, **kwargs)
		return get_pdf.call_args.args[0]

	def test_prints_rows_from_the_report_run(self):
		html = self.printed_html()

		self.assertIn("Renew the example.com domain", html)
		self.assertIn("Archive old invoices", html)

	def test_prints_only_the_visible_rows(self):
		descriptions = [row["description"] for row in run("ToDo")["result"]]
		html = self.printed_html(visible_idx=[descriptions.index("Renew the example.com domain")])

		self.assertIn("Renew the example.com domain", html)
		self.assertNotIn("Archive old invoices", html)

	def test_prints_only_the_picked_columns(self):
		html = self.printed_html(columns=["priority"])

		self.assertIn("High", html)
		self.assertNotIn("Renew the example.com domain", html)

	def test_prints_a_value_that_does_not_fit_the_column_type(self):
		report_run = {
			"columns": [{"fieldname": "date", "fieldtype": "Date"}],
			"result": [{"date": "Opening"}],
		}
		with patch("frappe.utils.print_format.run", return_value=report_run):
			html = self.printed_html()

		self.assertIn("Opening", html)

	def test_jinja_format_renders_the_report_run(self):
		html = self.printed_html(print_format=PF_TODO)

		self.assertIn('<h1 class="title">ToDo</h1>', html)
		self.assertIn('<p class="colcount">7</p>', html)

	def test_rejects_a_format_of_another_report(self):
		with self.assertRaises(frappe.ValidationError):
			download_report_pdf("ToDo", print_format=PF_JINJA)

	def test_requires_access_to_the_report(self):
		make_user_without_access()
		frappe.set_user(NO_ACCESS_USER)

		with self.assertRaises(frappe.PermissionError):
			download_report_pdf(REPORT)


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
	make_print_format(PF_JINJA, REPORT, "Jinja", css=".title { color: red; }")
	make_print_format(PF_JS, REPORT, "JS")
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


def make_report_user():
	user = frappe.new_doc("User")
	user.email = REPORT_USER
	user.first_name = "Report User"
	user.send_welcome_email = 0
	user.insert(ignore_permissions=True, ignore_if_duplicate=True)
	user.add_roles("System Manager")
