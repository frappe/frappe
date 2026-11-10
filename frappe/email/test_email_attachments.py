from typing import TYPE_CHECKING
from urllib.parse import quote

import requests

import frappe
from frappe.email.receive import InboundMail
from frappe.tests import IntegrationTestCase
from frappe.tests.utils.test_capabilities import TestService, requires_test_service
from frappe.utils import get_url

if TYPE_CHECKING:
	from frappe.core.doctype.file.file import File

EMAIL_CONTENT = """
Delivered-To: test@example.com
From: Test <test@example.com>
Date: Wed, 1 Jun 2024 12:00:00 +0000
Message-ID: <test@mail.example.com>
Subject: Test
To: Test <test@example.com>
Content-Type: multipart/mixed; boundary="ABC"

--ABC
Content-Type: application/pdf; name="t%C3%A9st%2542.txt"
Content-Disposition: attachment; filename="t%C3%A9st%2542.txt"
Content-Transfer-Encoding: base64
Content-ID: <test_content_id>
X-Attachment-Id: test_content_id

YWJjZGVmZ2hpamtsbW5vcF9hdHRhY2htZW50
--ABC--
""".strip()

ENCODED_FILENAME_EMAIL = """
From: Test <test@example.com>
Message-ID: <encoded-filename@mail.example.com>
Subject: Test
To: Test <test@example.com>
Content-Type: multipart/mixed; boundary="ABC"

--ABC
Content-Type: text/plain
Content-Disposition: attachment; filename="{filename}"
Content-Transfer-Encoding: base64

YWJj
--ABC--
""".strip()


class TestEmailAttachments(IntegrationTestCase):
	def test_email_attachment_percent_encoded(self):
		email_account = frappe._dict({"email_id": "receive@example.com"})
		mail = InboundMail(EMAIL_CONTENT, email_account)
		communication = mail.process()
		file: File = frappe.get_last_doc(
			"File",
			{
				"attached_to_doctype": communication.doctype,
				"attached_to_name": communication.name,
			},
		)  # type: ignore
		self.assertEqual(file.file_name, "tést%42.txt")
		file.save()
		self.assertEqual(file.file_name, "tést%42.txt")

	@requires_test_service(TestService.WEB_SERVER)
	def test_file_with_percent_in_filename(self):
		def make_and_check_file(index: int, literal_file_name: str, disk_file_name: str):
			content = "abcdefghijklmnop_attachment"
			file: File = frappe.new_doc("File")  # type: ignore
			file.update(
				{
					"file_name": literal_file_name,
					"is_private": 0,
					"content": f"{content}{index}",
				}
			)
			file.save()

			# Check that the file name is kept as is
			self.assertEqual(file.file_name, literal_file_name)

			# Check that the file URL is not encoded
			self.assertEqual(file.file_url, "/files/" + disk_file_name)

			# Try to download the file, first quoting it
			# To download a file named "test%42.txt", we would need to request "test%2542.txt", which is confusing
			# Instead, we should request "test_42.txt", which is the actual file name
			assert file.file_url

			res = requests.get(get_url(quote(file.file_url)))
			res.raise_for_status()

			res = requests.get(get_url("/files/" + disk_file_name))
			res.raise_for_status()

			# Saving again should not change the file_name or file_url
			values = file.as_dict()
			file.save()
			self.assertEqual(file.file_name, literal_file_name)
			self.assertEqual(file.file_url, values["file_url"])

		make_and_check_file(1, "1test%2542.txt", "1test_2542.txt")
		make_and_check_file(2, "2test%42.txt", "2test_42.txt")
		make_and_check_file(3, "3test*.txt", "3test*.txt")

	def test_encoded_attachment_filename(self):
		email_account = frappe._dict({"email_id": "receive@example.com"})
		filenames = [
			("Rechnung =?UTF-8?Q?M=C3=BCller?=.txt", "Rechnung Müller.txt"),
			("=?iso-8859-1?Q?empty_word_=E0=E0=E0=E9.txt?=", "empty word àààé.txt"),
			("=?ISO-8859-1?Q?Gr=FC=DFe?=\n =?UTF-8?Q?_=E2=84=96_1.txt?=", "Grüße № 1.txt"),
		]

		for filename, expected in filenames:
			mail = InboundMail(ENCODED_FILENAME_EMAIL.format(filename=filename), email_account)
			self.assertEqual(mail.attachments[0]["fname"], expected)

		mail = InboundMail(ENCODED_FILENAME_EMAIL.format(filename="=?UTF-8?Q??="), email_account)
		self.assertTrue(mail.attachments[0]["fname"].endswith(".txt"))
