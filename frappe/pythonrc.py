#!/usr/bin/env python2.7

# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import os
import frappe
frappe.connect(site=os.environ.get("site"))