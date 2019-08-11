# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import json
from frappe.model.document import Document
from frappe.frappeclient import FrappeClient

class NodeConfiguration(Document):
	def before_insert(self):
		config_exists = frappe.db.get_all(
			doctype = 'Node Configuration', 
			filters = [
				['master_node', '=', self.master_node],
				['follower_node', '=', self.follower_node]
			]
		)
		if config_exists:
			frappe.throw(_('Node Configuration already exists'))

@frappe.whitelist()
def sync_master_data():
	'''Sync master data to all follower nodes, triggered when update log is created'''
	current_node = frappe.utils.get_url()
	port = frappe.conf.http_port or frappe.conf.webserver_port
	current_node = current_node + ':' + str(port)

	node_configurations = frappe.get_all(
		doctype = 'Node Configuration',
		filters = {'master_node': current_node},
		group_by = 'follower_node'
	)

	for node_config in node_configurations:
		config = frappe.get_doc('Node Configuration', node_config.name)

		last_updated = frappe.db.get_value('Node', config.follower_node, 'last_updated')
		last_update_synced = frappe.db.get_value('Update Log', last_updated, 'creation')
		
		doctypes = []
		for entry in config.following_doctypes:
			doctypes.append(entry.ref_doctype)

		updates_to_be_synced = frappe.get_all(
			doctype = 'Update Log',
			filters = [['creation', '>', last_update_synced], ['ref_doctype', 'in', doctypes]],
			fields = ['update_type', 'ref_doctype', 'docname', 'data', 'name'],
			order_by = 'creation'
		)

		if updates_to_be_synced != []:
			client = FrappeClient(config.follower_node, 'Administrator', 'root')
			
			for doc in updates_to_be_synced:
				if doc.update_type == 'Create':
					client.insert(json.loads(doc.data))
				elif doc.update_type == 'Update':
					client.update(json.loads(doc.data))
				elif doc.update == 'Delete':
					client.delete(doc.ref_doctype, doc.docname)

			#set the last update for node
			frappe.db.set_value('Node', config.follower_node, 'last_updated', updates_to_be_synced[-1].get('name'))
			