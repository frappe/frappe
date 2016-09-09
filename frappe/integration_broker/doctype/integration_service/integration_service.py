# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue, get_jobs
import json, urlparse
from frappe.utils import get_request_session

class IntegrationService(Document):		
	def on_update(self):
		if self.enabled:
			self.enable_service()
			self.install_fixtures()

	def get_controller(self):
		if not getattr(self, '_controller', None):
			self._controller = get_integration_controller(self.service, setup=False)
		return self._controller

	def get_parameters(self):
		parameters = {}
		if self.custom_settings_json:
			parameters = json.loads(self.custom_settings_json)
		return parameters	

	def install_fixtures(self):
		pass

	def enable_service(self):
		if not self.flags.ignore_mandatory:
			self.get_controller().enable(self.get_parameters(), self.use_test_account)

	def setup_events_and_parameters(self):
		self.parameters = []
		for d in self.get_controller().parameters_template:
			self.parameters.append({'label': d.label, "value": d.value})

		self.events = []
		for d in self.get_controller()._events:
			self.parameters.append({'event': d.event, 'enabled': d.enabled})

	#rest request handler
	def get_request(self, url, auth=None, data=None):
		if not auth:
			auth = ''
		if not data:
			data = {}

		try:
			s = get_request_session()
			res = s.get(url, data={}, auth=auth)
			res.raise_for_status()
			return res.json()

		except Exception, exc:
			raise exc
	
	def post_request(self, url, auth=None, data=None):
		if not auth:
			auth = ''
		if not data:
			data = {}
		try:
			s = get_request_session()
			res = s.post(url, data=data, auth=auth)
			res.raise_for_status()
			
			if res.headers.get("content-type") == "text/plain; charset=utf-8":
				return urlparse.parse_qs(res.text)
		
			return res.json()
		except Exception, exc:
			raise exc
	
	def put_request(url, auth=None, data=None):
		pass
	
	def create_request(self, data, integration_type, service_name, name=None):
		if not isinstance(data, basestring):
			data = json.dumps(data)
	
		integration_request = frappe.get_doc({
			"doctype": "Integration Request",
			"integration_type": integration_type,
			"integration_request_service": service_name,
			"data": data
		})
		
		if name:
			integration_request.flags._name = name
		
		integration_request.insert(ignore_permissions=True)
		frappe.db.commit()

		return integration_request

@frappe.whitelist()
def get_service_parameters(service):
	controller = get_integration_controller(service, setup=False)
	return {
		'parameters': controller.parameters_template,
	}

@frappe.whitelist()
def get_js_resouce(service):
	controller = get_integration_controller(service, setup=False)
	return {
		"js": getattr(controller, "js", "")
	}
		
def get_integration_controller(service_name, setup=True):
	'''Returns integration controller module from app_name.integrations.{service}'''
	def load_from_app(app, service_name):
		try:
			controller_module = frappe.get_module("{app}.integrations.{service}"
				.format(app=app, service=service_name.strip().lower().replace(' ','_')))
			controller = controller_module.Controller(setup=setup)

			# make default properites and frappe._dictify
			for key in ('events', 'parameters_template'):
				tmp = []
				for d in getattr(controller, key, []):
					tmp.append(frappe._dict(d))
				setattr(controller, key, tmp)
			
			return controller

		except ImportError:
			pass
					
	for app in frappe.get_installed_apps():
		controller = load_from_app(app, service_name)
		if controller:
			return controller

	frappe.throw(_("Module {service} not found".format(service=service_name)))

@frappe.whitelist()
def get_integration_services():
	services = [""]
	for app in frappe.get_installed_apps():
		services.extend(frappe.get_hooks("integration_services", app_name = app))
	
	return services

def trigger_integration_service_events():
	for service in frappe.get_all("Integration Service", filters={"enabled": 1}, fields=["name"]):
		controller = get_integration_controller(service.name, setup=False)
		
		if hasattr(controller, "scheduled_jobs"):
			for job in controller.scheduled_jobs:
				for event, handlers in job.items():
					for handler in handlers:
						if handler not in get_jobs():
							enqueue(handler, queue='short', event=event)
