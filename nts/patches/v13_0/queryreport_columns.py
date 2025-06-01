# Copyright (c) 2021, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import nts


def execute():
	"""Convert Query Report json to support other content"""
	records = nts.get_all("Report", filters={"json": ["!=", ""]}, fields=["name", "json"])
	for record in records:
		jstr = record["json"]
		data = json.loads(jstr)
		if isinstance(data, list):
			# double escape braces
			jstr = f'{{"columns":{jstr}}}'
			nts.db.set_value("Report", record["name"], "json", jstr)
