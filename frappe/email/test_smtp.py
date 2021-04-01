# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: The MIT License

import unittest
from frappe.email.smtp import SMTPServer

class TestSMTP(unittest.TestCase):
	def test_smtp_ssl_session(self):
		for port in [None, 0, 465, "465"]:
			make_server(port, 1, 0)

	def test_smtp_tls_session(self):
		for port in [None, 0, 587, "587"]:
			make_server(port, 0, 1)


def make_server(port, ssl, tls):
	server = SMTPServer(
		server = "smtp.gmail.com",
		port = port,
		use_ssl = ssl,
		use_tls = tls
	)

	server.sess