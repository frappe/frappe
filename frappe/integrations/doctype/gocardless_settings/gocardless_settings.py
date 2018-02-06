# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import gocardless_pro
from frappe import _
from six.moves.urllib.parse import urlencode
from frappe.utils import get_url, call_hook_method, flt
from frappe.integrations.utils import create_request_log, create_payment_gateway

class GoCardlessSettings(Document):
	pass
