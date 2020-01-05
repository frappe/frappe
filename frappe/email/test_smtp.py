# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals

import unittest, os, base64
from frappe.email.smtp import (get_outgoing_email_account, get_default_outgoing_email_account)


class TestEmailAccount(unittest.TestCase):
  
  def setUp(self):

    pass

  def test_default_email_account(self):

    self.assetEqual(get_outgoing_email_account(), get_default_outgoing_email_account())