# Copyright (c) 2022, nts and Contributors
# License: MIT. See LICENSE


import nts
from nts.model import data_field_options


def execute():
	custom_field = nts.qb.DocType("Custom Field")
	(
		nts.qb.update(custom_field)
		.set(custom_field.options, None)
		.where((custom_field.fieldtype == "Data") & (custom_field.options.notin(data_field_options)))
	).run()
