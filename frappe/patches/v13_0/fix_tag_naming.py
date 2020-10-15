# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import re
import frappe


def execute():
	to_replace = ["&lt", "&gt", "&quot", "&#x27", "&#x2F"]

	or_filters = [["Tag", "name", "like", "%{}%".format(entity)] for entity in to_replace]
	tags = frappe.get_all("Tag", or_filters=or_filters)

	if not tags:
		return

	regex_rules = [re.compile("({});?".format(entity)) for entity in to_replace]

	for tag in tags:
		new_name = tag.name
		for rule in regex_rules:
			new_name = re.sub(rule, r"\1;", new_name)

		if tag.name != new_name:
			frappe.rename_doc("Tag", tag.name, new_name, force=True)
