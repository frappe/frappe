# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest
from werkzeug.wrappers import Response
from frappe.app import process_response

HEADERS = ('Access-Control-Allow-Origin', 'Access-Control-Allow-Credentials',
    'Access-Control-Allow-Methods', 'Access-Control-Allow-Headers')

class TestCORS(unittest.TestCase):
    def make_request_and_test(self, origin='http://example.com', absent=False):
        self.origin = origin

        headers = {}
        if origin:
            headers = {'Origin': origin}

        frappe.utils.set_request(headers=headers)

        self.response = Response()
        process_response(self.response)

        for header in HEADERS:
            if absent:
                self.assertNotIn(header, self.response.headers)
            else:
                if header == 'Access-Control-Allow-Origin':
                    self.assertEqual(self.response.headers.get(header), self.origin)
                else:
                    self.assertIn(header, self.response.headers)

    def test_cors_disabled(self):
        frappe.conf.allow_cors = None
        self.make_request_and_test('http://example.com', True)

    def test_request_without_origin(self):
        frappe.conf.allow_cors = 'http://example.com'
        self.make_request_and_test(None, True)

    def test_valid_origin(self):
        frappe.conf.allow_cors = 'http://example.com'
        self.make_request_and_test()

        frappe.conf.allow_cors = "*"
        self.make_request_and_test()

        frappe.conf.allow_cors = ['http://example.com', 'https://example.com']
        self.make_request_and_test()

    def test_invalid_origin(self):
        frappe.conf.allow_cors = 'http://example1.com'
        self.make_request_and_test(absent=True)

        frappe.conf.allow_cors = ['http://example1.com', 'https://example.com']
        self.make_request_and_test(absent=True)
