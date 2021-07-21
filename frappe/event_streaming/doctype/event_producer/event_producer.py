# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import time
import requests
from six import iteritems
from frappe import _
from frappe.model.document import Document
from frappe.frappeclient import FrappeClient
from frappe.utils.background_jobs import get_jobs
from frappe.utils.data import get_url, get_link_to_form
from frappe.utils.password import get_decrypted_password
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


class EventProducer(Document):
	def before_insert(self):
		self.check_url()
		self.validate_event_subscriber()
		self.incoming_change = True
		self.create_event_consumer()
		self.create_custom_fields()

	def validate(self):
		self.validate_event_subscriber()
		if frappe.flags.in_test:
			for entry in self.producer_doctypes:
				entry.status = 'Approved'

	def validate_event_subscriber(self):
		if not frappe.db.get_value('User', self.user, 'api_key'):
			frappe.throw(_('Please generate keys for the Event Subscriber User {0} first.').format(
				frappe.bold(get_link_to_form('User', self.user))
			))

	def on_update(self):
		if not self.incoming_change:
			if frappe.db.exists('Event Producer', self.name):
				if not self.api_key or not self.api_secret:
					frappe.throw(_('Please set API Key and Secret on the producer and consumer sites first.'))
				else:
					doc_before_save = self.get_doc_before_save()
					if doc_before_save.api_key != self.api_key or doc_before_save.api_secret != self.api_secret:
						return

					self.update_event_consumer()
					self.create_custom_fields()
		else:
			# when producer doc is updated it updates the consumer doc, set flag to avoid deadlock
			self.db_set('incoming_change', 0)
			self.reload()

	def check_url(self):
		valid_url_schemes = ("http", "https")
		frappe.utils.validate_url(self.producer_url, throw=True, valid_schemes=valid_url_schemes)

		# remove '/' from the end of the url like http://test_site.com/
		# to prevent mismatch in get_url() results
		if self.producer_url.endswith("/"):
			self.producer_url = self.producer_url[:-1]

	def create_event_consumer(self):
		"""register event consumer on the producer site"""
		if self.is_producer_online():
			producer_site = FrappeClient(
				url=self.producer_url,
				api_key=self.api_key,
				api_secret=self.get_password('api_secret')
			)

			response = producer_site.post_api(
				'frappe.event_streaming.doctype.event_consumer.event_consumer.register_consumer',
				params={'data': json.dumps(self.get_request_data())}
			)
			if response:
				response = json.loads(response)
				self.set_last_update(response['last_update'])
			else:
				frappe.throw(_('Failed to create an Event Consumer or an Event Consumer for the current site is already registered.'))

	def set_last_update(self, last_update):
		last_update_doc_name = frappe.db.get_value('Event Producer Last Update', dict(event_producer=self.name))
		if not last_update_doc_name:
			frappe.get_doc(dict(
				doctype = 'Event Producer Last Update',
				event_producer = self.producer_url,
				last_update = last_update
			)).insert(ignore_permissions=True)
		else:
			frappe.db.set_value('Event Producer Last Update', last_update_doc_name, 'last_update', last_update)

	def get_last_update(self):
		return frappe.db.get_value('Event Producer Last Update', dict(event_producer=self.name), 'last_update')

	def get_request_data(self):
		consumer_doctypes = []
		for entry in self.producer_doctypes:
			if entry.has_mapping:
				# if mapping, subscribe to remote doctype on consumer's site
				dt = frappe.db.get_value('Document Type Mapping', entry.mapping, 'remote_doctype')
			else:
				dt = entry.ref_doctype
			consumer_doctypes.append({
				"doctype": dt,
				"condition": entry.condition
			})

		user_key = frappe.db.get_value('User', self.user, 'api_key')
		user_secret = get_decrypted_password('User', self.user, 'api_secret')
		return {
			'event_consumer': get_url(),
			'consumer_doctypes': json.dumps(consumer_doctypes),
			'user': self.user,
			'api_key': user_key,
			'api_secret': user_secret
		}

	def create_custom_fields(self):
		"""create custom field to store remote docname and remote site url"""
		for entry in self.producer_doctypes:
			if not entry.use_same_name:
				if not frappe.db.exists('Custom Field', {'fieldname': 'remote_docname', 'dt': entry.ref_doctype}):
					df = dict(fieldname='remote_docname', label='Remote Document Name', fieldtype='Data', read_only=1, print_hide=1)
					create_custom_field(entry.ref_doctype, df)
				if not frappe.db.exists('Custom Field', {'fieldname': 'remote_site_name', 'dt': entry.ref_doctype}):
					df = dict(fieldname='remote_site_name', label='Remote Site', fieldtype='Data', read_only=1, print_hide=1)
					create_custom_field(entry.ref_doctype, df)

	def update_event_consumer(self):
		if self.is_producer_online():
			producer_site = get_producer_site(self.producer_url)
			event_consumer = producer_site.get_doc('Event Consumer', get_url())
			event_consumer = frappe._dict(event_consumer)
			if event_consumer:
				config = event_consumer.consumer_doctypes
				event_consumer.consumer_doctypes = []
				for entry in self.producer_doctypes:
					if entry.has_mapping:
						# if mapping, subscribe to remote doctype on consumer's site
						ref_doctype = frappe.db.get_value('Document Type Mapping', entry.mapping, 'remote_doctype')
					else:
						ref_doctype = entry.ref_doctype

					event_consumer.consumer_doctypes.append({
						'ref_doctype': ref_doctype,
						'status': get_approval_status(config, ref_doctype),
						'unsubscribed': entry.unsubscribe,
						'condition': entry.condition
					})
				event_consumer.user = self.user
				event_consumer.incoming_change = True
				producer_site.update(event_consumer)

	def is_producer_online(self):
		"""check connection status for the Event Producer site"""
		retry = 3
		while retry > 0:
			res = requests.get(self.producer_url)
			if res.status_code == 200:
				return True
			retry -= 1
			time.sleep(5)
		frappe.throw(_('Failed to connect to the Event Producer site. Retry after some time.'))


def get_producer_site(producer_url):
	"""create a FrappeClient object for event producer site"""
	producer_doc = frappe.get_doc('Event Producer', producer_url)
	producer_site = FrappeClient(
		url=producer_url,
		api_key=producer_doc.api_key,
		api_secret=producer_doc.get_password('api_secret')
	)
	return producer_site


def get_approval_status(config, ref_doctype):
	"""check the approval status for consumption"""
	for entry in config:
		if entry.get('ref_doctype') == ref_doctype:
			return entry.get('status')
	return 'Pending'


@frappe.whitelist()
def pull_producer_data():
	"""Fetch data from producer node."""
	response = requests.get(get_url())
	if response.status_code == 200:
		for event_producer in frappe.get_all('Event Producer'):
			pull_from_node(event_producer.name)
		return 'success'
	return None


@frappe.whitelist()
def pull_from_node(event_producer):
	"""pull all updates after the last update timestamp from event producer site"""
	event_producer = frappe.get_doc('Event Producer', event_producer)
	producer_site = get_producer_site(event_producer.producer_url)
	last_update = event_producer.get_last_update()

	(doctypes, mapping_config, naming_config) = get_config(event_producer.producer_doctypes)

	updates = get_updates(producer_site, last_update, doctypes)

	for update in updates:
		update.use_same_name = naming_config.get(update.ref_doctype)
		mapping = mapping_config.get(update.ref_doctype)
		if mapping:
			update.mapping = mapping
			update = get_mapped_update(update, producer_site)
		if not update.update_type == 'Delete':
			update.data = json.loads(update.data)

		sync(update, producer_site, event_producer)


def get_config(event_config):
	"""get the doctype mapping and naming configurations for consumption"""
	doctypes, mapping_config, naming_config = [], {}, {}

	for entry in event_config:
		if entry.status == 'Approved':
			if entry.has_mapping:
				(mapped_doctype, mapping) = frappe.db.get_value('Document Type Mapping', entry.mapping, ['remote_doctype', 'name'])
				mapping_config[mapped_doctype] = mapping
				naming_config[mapped_doctype] = entry.use_same_name
				doctypes.append(mapped_doctype)
			else:
				naming_config[entry.ref_doctype] = entry.use_same_name
				doctypes.append(entry.ref_doctype)
	return (doctypes, mapping_config, naming_config)


def sync(update, producer_site, event_producer, in_retry=False):
	"""Sync the individual update"""
	try:
		if update.update_type == 'Create':
			set_insert(update, producer_site, event_producer.name)
		if update.update_type == 'Update':
			set_update(update, producer_site)
		if update.update_type == 'Delete':
			set_delete(update)
		if in_retry:
			return 'Synced'
		log_event_sync(update, event_producer.name, 'Synced')

	except Exception:
		if in_retry:
			if frappe.flags.in_test:
				print(frappe.get_traceback())
			return 'Failed'
		log_event_sync(update, event_producer.name, 'Failed', frappe.get_traceback())

	event_producer.set_last_update(update.creation)
	frappe.db.commit()


def set_insert(update, producer_site, event_producer):
	"""Sync insert type update"""
	if frappe.db.get_value(update.ref_doctype, update.docname):
		# doc already created
		return
	doc = frappe.get_doc(update.data)

	if update.mapping:
		if update.get('dependencies'):
			dependencies_created = sync_mapped_dependencies(update.dependencies, producer_site)
			for fieldname, value in iteritems(dependencies_created):
				doc.update({ fieldname : value })
	else:
		sync_dependencies(doc, producer_site)

	if update.use_same_name:
		doc.insert(set_name=update.docname, set_child_names=False)
	else:
		# if event consumer is not saving documents with the same name as the producer
		# store the remote docname in a custom field for future updates
		local_doc = doc.insert(set_child_names=False)
		set_custom_fields(local_doc, update.docname, event_producer)


def set_update(update, producer_site):
	"""Sync update type update"""
	local_doc = get_local_doc(update)
	if local_doc:
		data = frappe._dict(update.data)

		if data.changed:
			local_doc.update(data.changed)
		if data.removed:
			local_doc = update_row_removed(local_doc, data.removed)
		if data.row_changed:
			update_row_changed(local_doc, data.row_changed)
		if data.added:
			local_doc = update_row_added(local_doc, data.added)

		if update.mapping:
			if update.get('dependencies'):
				dependencies_created = sync_mapped_dependencies(update.dependencies, producer_site)
				for fieldname, value in iteritems(dependencies_created):
					local_doc.update({ fieldname : value })
		else:
			sync_dependencies(local_doc, producer_site)

		local_doc.save()
		local_doc.db_update_all()


def update_row_removed(local_doc, removed):
	"""Sync child table row deletion type update"""
	for tablename, rownames in iteritems(removed):
		table = local_doc.get_table_field_doctype(tablename)
		for row in rownames:
			table_rows = local_doc.get(tablename)
			child_table_row = get_child_table_row(table_rows, row)
			table_rows.remove(child_table_row)
			local_doc.set(tablename, table_rows)
	return local_doc


def get_child_table_row(table_rows, row):
	for entry in table_rows:
		if entry.get('name') == row:
			return entry


def update_row_changed(local_doc, changed):
	"""Sync child table row updation type update"""
	for tablename, rows in iteritems(changed):
		old = local_doc.get(tablename)
		for doc in old:
			for row in rows:
				if row['name'] == doc.get('name'):
					doc.update(row)


def update_row_added(local_doc, added):
	"""Sync child table row addition type update"""
	for tablename, rows in iteritems(added):
		local_doc.extend(tablename, rows)
		for child in rows:
			child_doc = frappe.get_doc(child)
			child_doc.parent = local_doc.name
			child_doc.parenttype = local_doc.doctype
			child_doc.insert(set_name=child_doc.name)
	return local_doc


def set_delete(update):
	"""Sync delete type update"""
	local_doc = get_local_doc(update)
	if local_doc:
		local_doc.delete()


def get_updates(producer_site, last_update, doctypes):
	"""Get all updates generated after the last update timestamp"""
	docs = producer_site.post_request({
			'cmd': 'frappe.event_streaming.doctype.event_update_log.event_update_log.get_update_logs_for_consumer',
			'event_consumer': get_url(),
			'doctypes': frappe.as_json(doctypes),
			'last_update': last_update
	})
	return [frappe._dict(d) for d in (docs or [])]


def get_local_doc(update):
	"""Get the local document if created with a different name"""
	try:
		if not update.use_same_name:
			return frappe.get_doc(update.ref_doctype, {'remote_docname': update.docname})
		return frappe.get_doc(update.ref_doctype, update.docname)
	except frappe.DoesNotExistError:
		return None


def sync_dependencies(document, producer_site):
	"""
	dependencies is a dictionary to store all the docs
	having dependencies and their sync status,
	which is shared among all nested functions.
	"""
	dependencies = {document: True}

	def check_doc_has_dependencies(doc, producer_site):
		"""Sync child table link fields first,
		then sync link fields,
		then dynamic links"""
		meta = frappe.get_meta(doc.doctype)
		table_fields = meta.get_table_fields()
		link_fields = meta.get_link_fields()
		dl_fields = meta.get_dynamic_link_fields()
		if table_fields:
			sync_child_table_dependencies(doc, table_fields, producer_site)
		if link_fields:
			sync_link_dependencies(doc, link_fields, producer_site)
		if dl_fields:
			sync_dynamic_link_dependencies(doc, dl_fields, producer_site)

	def sync_child_table_dependencies(doc, table_fields, producer_site):
		for df in table_fields:
			child_table = doc.get(df.fieldname)
			for entry in child_table:
				child_doc = producer_site.get_doc(entry.doctype, entry.name)
				child_doc = frappe._dict(child_doc)
				set_dependencies(child_doc, frappe.get_meta(entry.doctype).get_link_fields(), producer_site)

	def sync_link_dependencies(doc, link_fields, producer_site):
		set_dependencies(doc, link_fields, producer_site)

	def sync_dynamic_link_dependencies(doc, dl_fields, producer_site):
		for df in dl_fields:
			docname = doc.get(df.fieldname)
			linked_doctype = doc.get(df.options)
			if docname and not check_dependency_fulfilled(linked_doctype, docname):
				master_doc = producer_site.get_doc(linked_doctype, docname)
				frappe.get_doc(master_doc).insert(set_name=docname)

	def set_dependencies(doc, link_fields, producer_site):
		for df in link_fields:
			docname = doc.get(df.fieldname)
			linked_doctype = df.get_link_doctype()
			if docname and not check_dependency_fulfilled(linked_doctype, docname):
				master_doc = producer_site.get_doc(linked_doctype, docname)
				try:
					master_doc = frappe.get_doc(master_doc)
					master_doc.insert(set_name=docname)
					frappe.db.commit()

				# for dependency inside a dependency
				except Exception:
					dependencies[master_doc] = True

	def check_dependency_fulfilled(linked_doctype, docname):
		return frappe.db.exists(linked_doctype, docname)

	while dependencies[document]:
		# find the first non synced dependency
		for item in reversed(list(dependencies.keys())):
			if dependencies[item]:
				dependency = item
				break

		check_doc_has_dependencies(dependency, producer_site)

		# mark synced for nested dependency
		if dependency != document:
			dependencies[dependency] = False
			dependency.insert()

		# no more dependencies left to be synced, the main doc is ready to be synced
		# end the dependency loop
		if not any(list(dependencies.values())[1:]):
			dependencies[document] = False


def sync_mapped_dependencies(dependencies, producer_site):
	dependencies_created = {}
	for entry in dependencies:
		doc = frappe._dict(json.loads(entry[1]))
		docname = frappe.db.exists(doc.doctype, doc.name)
		if not docname:
			doc = frappe.get_doc(doc).insert(set_child_names=False)
			dependencies_created[entry[0]] = doc.name
		else:
			dependencies_created[entry[0]] = docname

	return dependencies_created

def log_event_sync(update, event_producer, sync_status, error=None):
	"""Log event update received with the sync_status as Synced or Failed"""
	doc = frappe.new_doc('Event Sync Log')
	doc.update_type = update.update_type
	doc.ref_doctype = update.ref_doctype
	doc.status = sync_status
	doc.event_producer = event_producer
	doc.producer_doc = update.docname
	doc.data = frappe.as_json(update.data)
	doc.use_same_name = update.use_same_name
	doc.mapping = update.mapping if update.mapping else None
	if update.use_same_name:
		doc.docname = update.docname
	else:
		doc.docname = frappe.db.get_value(update.ref_doctype, {'remote_docname': update.docname}, 'name')
	if error:
		doc.error = error
	doc.insert()


def get_mapped_update(update, producer_site):
	"""get the new update document with mapped fields"""
	mapping = frappe.get_doc('Document Type Mapping', update.mapping)
	if update.update_type == 'Create':
		doc = frappe._dict(json.loads(update.data))
		mapped_update = mapping.get_mapping(doc, producer_site, update.update_type)
		update.data = mapped_update.get('doc')
		update.dependencies = mapped_update.get('dependencies', None)
	elif update.update_type == 'Update':
		mapped_update = mapping.get_mapped_update(update, producer_site)
		update.data = mapped_update.get('doc')
		update.dependencies = mapped_update.get('dependencies', None)

	update['ref_doctype'] = mapping.local_doctype
	return update


@frappe.whitelist()
def new_event_notification(producer_url):
	"""Pull data from producer when notified"""
	enqueued_method = 'frappe.event_streaming.doctype.event_producer.event_producer.pull_from_node'
	jobs = get_jobs()
	if not jobs or enqueued_method not in jobs[frappe.local.site]:
		frappe.enqueue(enqueued_method, queue='default', **{'event_producer': producer_url})


@frappe.whitelist()
def resync(update):
	"""Retry syncing update if failed"""
	update = frappe._dict(json.loads(update))
	producer_site = get_producer_site(update.event_producer)
	event_producer = frappe.get_doc('Event Producer', update.event_producer)
	if update.mapping:
		update = get_mapped_update(update, producer_site)
		update.data = json.loads(update.data)
	return sync(update, producer_site, event_producer, in_retry=True)


def set_custom_fields(local_doc, remote_docname, remote_site_name):
	"""sets custom field in doc for storing remote docname"""
	frappe.db.set_value(local_doc.doctype, local_doc.name, 'remote_docname', remote_docname)
	frappe.db.set_value(local_doc.doctype, local_doc.name, 'remote_site_name', remote_site_name)
