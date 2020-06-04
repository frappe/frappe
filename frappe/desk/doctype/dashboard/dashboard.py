# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files
import frappe
from frappe import _
import json
from frappe.utils.dashboard import create_filters_file_after_export

class Dashboard(Document):
	def on_update(self):
		if self.is_default:
			# make all other dashboards non-default
			frappe.db.sql('''update
				tabDashboard set is_default = 0 where name != %s''', self.name)

	def validate(self):
		if not frappe.conf.developer_mode and self.is_standard:
			frappe.throw('Cannot edit Standard Dashboards')
		self.validate_custom_options()

	def validate_custom_options(self):
		if self.chart_options:
			try:
				json.loads(self.chart_options)
			except ValueError as error:
				frappe.throw(_("Invalid json added in the custom options: {0}").format(error))

@frappe.whitelist()
def export_dashboard(doc):
	doc = frappe._dict(frappe.parse_json(doc))
	card_count = 0
	chart_count = 0

	if not doc.module:
		frappe.msgprint(_('Please set Module'))

	if frappe.conf.developer_mode and doc.module:
		export_to_files(record_list=[['Dashboard', doc.name, doc.module + ' Dashboard']], record_module=doc.module,)
		record_list = []
		for chart in doc.charts:
			record_list.append(['Dashboard Chart', chart.get('chart'), 'Dashboard Charts'])
			chart_count+=1
		for card in doc.cards:
			record_list.append(['Number Card', card.get('card'), 'Number Cards'])
			card_count+=1

		export_to_files(record_list=record_list, record_module=doc.module)
		frappe.msgprint(_('Successfully exported <b>{chart_count} Charts</b> and <b>{card_count} Cards</b>').format(chart_count=chart_count, card_count=card_count))

		create_filters_file_after_export(module_name=doc.module.lower(), dashboard_name=doc.name)

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
