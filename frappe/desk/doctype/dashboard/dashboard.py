# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe.model.document import Document
import frappe
from frappe import _
import json

class Dashboard(Document):
	def on_update(self):
		if self.is_default:
			# make all other dashboards non-default
			frappe.db.sql('''update
				tabDashboard set is_default = 0 where name != %s''', self.name)

	def validate(self):
		self.validate_custom_options()

	def validate_custom_options(self):
		if self.chart_options:
			try:
				json.loads(self.chart_options)
			except ValueError as error:
				frappe.throw(_("Invalid json added in the custom options: {0}").format(error))

@frappe.whitelist()
def get_permitted_charts(dashboard_name):
	permitted_charts = []
	dashboard = frappe.get_doc('Dashboard', dashboard_name)
	for chart in dashboard.charts:
		if frappe.has_permission('Dashboard Chart', doc=chart.chart):
			chart_dict = frappe._dict()
			chart_dict.update(chart.as_dict())

			if dashboard.get('chart_options'):
				chart_dict.custom_options = dashboard.get('chart_options')
			permitted_charts.append(chart_dict)

	return permitted_charts

@frappe.whitelist()
def get_permitted_cards(dashboard_name):
	permitted_cards = []
	dashboard = frappe.get_doc('Dashboard', dashboard_name)
	for card in dashboard.cards:
		if frappe.has_permission('Number Card', doc=card.card):
			permitted_cards.append(card)
	return permitted_cards
