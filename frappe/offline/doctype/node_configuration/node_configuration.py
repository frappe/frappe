# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import json
from frappe.model.document import Document
from frappe.frappeclient import FrappeClient
from frappe.model.document import check_doctype_has_followers
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

class NodeConfiguration(Document):
	def before_insert(self):
		config_exists = frappe.db.get_all(
			doctype = 'Node Configuration',
			filters = {
				'master_node': self.master_node,
				'follower_node': self.follower_node
			}
		)
		if config_exists:
			frappe.throw(_('Node configuration already exists'))
		
@frappe.whitelist()
def pull_master_data():
	'''Fetch data from remote master node.'''
	for node_config in frappe.get_all('Node Configuration', {'follower_node': get_current_node().name}):
		pull_from_node(node_config.name)
	return 'success'

def pull_from_node(node_config_name):
	config = frappe.get_doc('Node Configuration', node_config_name)
	master = get_master(config)
	last_update = frappe.db.get_value('Node', config.follower_node, 'last_updated')
	doctypes = []
	for entry in config.following_doctypes:
		doctypes.append(entry.ref_doctype)

	updates = get_updates(master, last_update, doctypes)

	for update in updates:
		if update.update_type == 'Create':
			set_insert(update)

		if update.update_type == 'Update':
			set_update(update)

		if update.update_type == 'Delete':
			set_delete(update)

		frappe.db.set_value('Node', config.follower_node, 'last_updated', update.name)
		frappe.db.commit()

def set_insert(update):
	if frappe.db.get_value(update.ref_doctype, dict(remote_docname=update.docname)):
		# doc already created
		return
	else:
		frappe.get_doc(json.loads(update.data)).insert(set_name=update.docname)

def set_update(update):
	local_doc = get_local_doc(update)
	data = json.loads(update.get('data'))
	data.pop('name')
	local_doc.update(data)
	local_doc.db_update_all()

def set_delete(update):
	get_local_doc(update).delete()

def get_updates(master, last_update, doctypes):
	last_update_timestamp = master.get_value('Update Log', 'creation', {'name': last_update}).get('creation')
	docs = master.get_list(
		doctype = 'Update Log',
		filters = {'creation': ('>', last_update_timestamp), 'ref_doctype': ('in', doctypes)},
		fields = ['update_type', 'ref_doctype', 'docname', 'data', 'name']
	)
	docs.reverse()
	return [frappe._dict(d) for d in docs]

def get_master(config):
	master = FrappeClient(config.master_node, 'Administrator', 'root')
	return master

def get_local_doc(update):
	return frappe.get_doc(update.ref_doctype, update.docname)

def get_current_node():
	current_node = frappe.utils.get_url()
	parts = current_node.split(':')
	if not len(parts) > 2:
		port = frappe.conf.http_port or frappe.conf.webserver_port
		current_node += ':' + str(port)

	return frappe.get_doc('Node', current_node)
