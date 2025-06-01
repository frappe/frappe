# Copyright (c) 2020, nts Technologies and contributors
# License: MIT. See LICENSE

import json

import nts

# import nts
from nts.model.document import Document


class DashboardSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		chart_config: DF.Code | None
		user: DF.Link | None
	# end: auto-generated types
	pass


@nts.whitelist()
def create_dashboard_settings(user):
	if not nts.db.exists("Dashboard Settings", user):
		doc = nts.new_doc("Dashboard Settings")
		doc.name = user
		doc.insert(ignore_permissions=True)
		nts.db.commit()
		return doc


def get_permission_query_conditions(user):
	if not user:
		user = nts.session.user

	return f"""(`tabDashboard Settings`.name = {nts.db.escape(user)})"""


@nts.whitelist()
def save_chart_config(reset, config, chart_name):
	reset = nts.parse_json(reset)
	doc = nts.get_doc("Dashboard Settings", nts.session.user)
	chart_config = nts.parse_json(doc.chart_config) or {}

	if reset:
		chart_config[chart_name] = {}
	else:
		config = nts.parse_json(config)
		if chart_name not in chart_config:
			chart_config[chart_name] = {}
		chart_config[chart_name].update(config)

	nts.db.set_value("Dashboard Settings", nts.session.user, "chart_config", json.dumps(chart_config))
