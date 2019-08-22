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
from frappe.desk.form.linked_with import get_linked_doctypes

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
			set_insert(update, master)

		if update.update_type == 'Update':
			set_update(update, master)

		if update.update_type == 'Delete':
			set_delete(update)

		frappe.db.set_value('Node', config.follower_node, 'last_updated', update.name)
		frappe.db.commit()

def set_insert(update, master):
	if frappe.db.get_value(update.ref_doctype, update.docname):
		# doc already created
		return
	else:
		doc = frappe.get_doc(json.loads(update.data))
		check_doc_has_dependencies(doc, master)
		frappe.get_doc(json.loads(update.data)).insert(set_name=update.docname)

def set_update(update, master):
	local_doc = get_local_doc(update)
	data = json.loads(update.get('data'))
	data.pop('name')
	local_doc.update(data)
	local_doc.db_update_all()

def set_delete(update):
	local_doc = get_local_doc(update)
	if local_doc:
		local_doc.delete()

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
	try:
		return frappe.get_doc(update.ref_doctype, update.docname)
	except frappe.DoesNotExistError:
		return

def get_current_node():
	current_node = frappe.utils.get_url()
	parts = current_node.split(':')
	if not len(parts) > 2:
		port = frappe.conf.http_port or frappe.conf.webserver_port
		current_node += ':' + str(port)

	return frappe.get_doc('Node', current_node)

def check_doc_has_dependencies(doc, master):
	'''Sync child table link fields first,
	then sync link fields,
	then dynamic links'''

	meta = frappe.get_meta(doc.doctype)
	sync_child_table_dependencies(doc, meta.get_table_fields(), master)
	sync_link_dependencies(doc, master)
	sync_dynamic_link_dependencies(meta.get_dynamic_link_fields())
			
def sync_child_table_dependencies(doc, table_fields, master):
	for df in table_fields:
		child_table = doc.get(df.fieldname)
		for entry in child_table:
			set_dependencies(entry, master)
		
def sync_link_dependencies(doc, master):
	set_dependencies(doc, master)

def sync_dynamic_link_dependencies(dl_fields):
	pass

def set_dependencies(doc, master):
	meta = frappe.get_meta(doc.doctype)
	for df in meta.get_link_fields():
		docname = doc.get(df.fieldname)
		linked_doctype = df.get_link_doctype()
		if docname and not check_dependency_fulfilled(linked_doctype, docname):
			master_doc = master.get_doc(linked_doctype, docname)
			frappe.get_doc(master_doc).insert(set_name=docname)

def check_dependency_fulfilled(linked_doctype, docname):
	return frappe.db.exists(linked_doctype, docname)