# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import nts
from nts.test_runner import make_test_objects
from nts.tests.utils import ntsTestCase

test_records = nts.get_test_records("Email Domain")


class TestDomain(ntsTestCase):
	def setUp(self):
		make_test_objects("Email Domain", reset=True)

	def tearDown(self):
		nts.delete_doc("Email Account", "Test")
		nts.delete_doc("Email Domain", "test.com")

	def test_on_update(self):
		mail_domain = nts.get_doc("Email Domain", "test.com")
		mail_account = nts.get_doc("Email Account", "Test")

		# Ensure a different port
		mail_account.incoming_port = int(mail_domain.incoming_port) + 5
		mail_account.save()
		# Trigger update of accounts using this domain
		mail_domain.on_update()

		mail_account.reload()
		# After update, incoming_port in account should match the domain
		self.assertEqual(mail_account.incoming_port, mail_domain.incoming_port)

		# Also make sure that the other attributes match
		self.assertEqual(mail_account.use_imap, mail_domain.use_imap)
		self.assertEqual(mail_account.use_ssl, mail_domain.use_ssl)
		self.assertEqual(mail_account.use_starttls, mail_domain.use_starttls)
		self.assertEqual(mail_account.use_tls, mail_domain.use_tls)
		self.assertEqual(mail_account.attachment_limit, mail_domain.attachment_limit)
		self.assertEqual(mail_account.smtp_server, mail_domain.smtp_server)
		self.assertEqual(mail_account.smtp_port, mail_domain.smtp_port)
