#!/usr/bin/env python2.7

# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import os
import frappe
frappe.connect(site=os.environ.get("site"))