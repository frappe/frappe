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
		
	def on_update(self):
		''' create custom field to store remote docname of master node'''
		df = {
				'label': 'Remote Docname',
				'fieldname': 'remote_docname',
				'fieldtype': 'Data',
				'hidden': 1,
				'read_only': 1,
				'unique': 1,
				'no_copy': 1
			}
		for doc in self.following_doctypes:
			print(doc)
			create_custom_field(doc.ref_doctype, df)

@frappe.whitelist()
def pull_master_data():
	'''Fetch data from remote master node.'''
	current_node = frappe.utils.get_url()
	node_configurations = frappe.get_all(
		doctype = 'Node Configuration',
		filters = {'follower_node': current_node}
	)
	for node_config in node_configurations:
		config = frappe.get_doc('Node Configuration', node_config.name)
		client = FrappeClient(config.master_node, 'Administrator', 'root')
		remote_node = client.get_doc('Node', filters = {'host_name': current_node}, fields = ['name', 'last_updated'])
		last_update_synced = client.get_value('Update Log', 'creation', filters = {'name': remote_node[0].get('last_updated')})

		doctypes = []
		for entry in config.following_doctypes:
			doctypes.append(entry.ref_doctype)

		updates_to_be_synced = client.get_list(
			doctype = 'Update Log',
			filters = [['creation', '>', last_update_synced], ['ref_doctype', 'in', doctypes]],
			fields = ['update_type', 'ref_doctype', 'docname', 'data', 'name'],
		)

		if updates_to_be_synced != []:
			for doc in updates_to_be_synced:
				try:
					if doc.get('update_type') == 'Create':
						local_doc = frappe.get_doc(json.loads(doc.get('data'))).insert()
						doc = frappe.db.set_value(doc.get('ref_doctype'), local_doc.name, 'remote_docname', doc.get('name'))

					if doc.get('update_type') == 'Update':
						mapped_doc = frappe.get_all(doc.get('ref_doctype'), filters = {'remote_docname': doc.get('name')}, fields = ['name'])
						local_doc = frappe.get_doc(doc.get('doctype'), mapped_doc[0].get('name'))
						local_doc.update(json.loads(doc.get('data')))

					if doc.get('update_type') == 'Delete':
						mapped_doc = frappe.get_all(doc.get('ref_doctype'), filters = {'remote_docname': doc.get('name')}, fields = ['name'])				
						local_doc = frappe.get_doc(doc.get('doctype'), mapped_doc[0].get('name'))
						local_doc.delete()
					frappe.db.commit()

				except Exception:
					frappe.db.rollback()
					frappe.log_error(frappe.get_traceback(), _('Pulling master data failed'))
					return 'failed'

			client.set_value('Node', remote_node[0].get('name'), 'last_updated', updates_to_be_synced[-1].name)
		
		else:
			return 'no updates'
	
	return 'success'