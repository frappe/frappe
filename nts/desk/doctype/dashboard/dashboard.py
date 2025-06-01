# Copyright (c) 2022, nts Technologies and contributors
# License: MIT. See LICENSE

import json

import nts
from nts import _
from nts.config import get_modules_from_all_apps_for_user
from nts.model.document import Document
from nts.modules.export_file import export_to_files
from nts.query_builder import DocType


class Dashboard(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.desk.doctype.dashboard_chart_link.dashboard_chart_link import DashboardChartLink
		from nts.desk.doctype.number_card_link.number_card_link import NumberCardLink
		from nts.types import DF

		cards: DF.Table[NumberCardLink]
		chart_options: DF.Code | None
		charts: DF.Table[DashboardChartLink]
		dashboard_name: DF.Data
		is_default: DF.Check
		is_standard: DF.Check
		module: DF.Link | None

	# end: auto-generated types
	def on_update(self):
		if self.is_default:
			# make all other dashboards non-default
			DashBoard = DocType("Dashboard")

			nts.qb.update(DashBoard).set(DashBoard.is_default, 0).where(DashBoard.name != self.name).run()

		if nts.conf.developer_mode and self.is_standard:
			export_to_files(
				record_list=[["Dashboard", self.name, f"{self.module} Dashboard"]], record_module=self.module
			)

	def validate(self):
		if not nts.conf.developer_mode and self.is_standard:
			nts.throw(_("Cannot edit Standard Dashboards"))

		if self.is_standard:
			non_standard_docs_map = {
				"Dashboard Chart": get_non_standard_charts_in_dashboard(self),
				"Number Card": get_non_standard_cards_in_dashboard(self),
			}

			if non_standard_docs_map["Dashboard Chart"] or non_standard_docs_map["Number Card"]:
				message = get_non_standard_warning_message(non_standard_docs_map)
				nts.throw(message, title=_("Standard Not Set"), is_minimizable=True)

		self.validate_custom_options()

	def validate_custom_options(self):
		if self.chart_options:
			try:
				json.loads(self.chart_options)
			except ValueError as error:
				nts.throw(_("Invalid json added in the custom options: {0}").format(error))


def get_permission_query_conditions(user):
	if not user:
		user = nts.session.user

	if user == "Administrator" or "System Manager" in nts.get_roles(user):
		return

	module_not_set = " ifnull(`tabDashboard`.`module`, '') = '' "
	allowed_modules = [
		nts.db.escape(module.get("module_name")) for module in get_modules_from_all_apps_for_user()
	]
	if not allowed_modules:
		return module_not_set

	return f" (`tabDashboard`.`module` in ({','.join(allowed_modules)}) or {module_not_set}) "


@nts.whitelist()
def get_permitted_charts(dashboard_name):
	permitted_charts = []
	dashboard = nts.get_doc("Dashboard", dashboard_name)
	for chart in dashboard.charts:
		if nts.has_permission("Dashboard Chart", doc=chart.chart):
			chart_dict = nts._dict()
			chart_dict.update(chart.as_dict())

			if dashboard.get("chart_options"):
				chart_dict.custom_options = dashboard.get("chart_options")
			permitted_charts.append(chart_dict)

	return permitted_charts


@nts.whitelist()
def get_permitted_cards(dashboard_name):
	dashboard = nts.get_doc("Dashboard", dashboard_name)
	return [card for card in dashboard.cards if nts.has_permission("Number Card", doc=card.card)]


def get_non_standard_charts_in_dashboard(dashboard):
	non_standard_charts = [doc.name for doc in nts.get_list("Dashboard Chart", {"is_standard": 0})]
	return [chart_link.chart for chart_link in dashboard.charts if chart_link.chart in non_standard_charts]


def get_non_standard_cards_in_dashboard(dashboard):
	non_standard_cards = [doc.name for doc in nts.get_list("Number Card", {"is_standard": 0})]
	return [card_link.card for card_link in dashboard.cards if card_link.card in non_standard_cards]


def get_non_standard_warning_message(non_standard_docs_map):
	message = _("""Please set the following documents in this Dashboard as standard first.""")

	def get_html(docs, doctype):
		html = f"<p>{nts.bold(doctype)}</p>"
		for doc in docs:
			html += f'<div><a href="/app/Form/{doctype}/{doc}">{doc}</a></div>'
		html += "<br>"
		return html

	html = message + "<br>"

	for doctype in non_standard_docs_map:
		if non_standard_docs_map[doctype]:
			html += get_html(non_standard_docs_map[doctype], doctype)

	return html
