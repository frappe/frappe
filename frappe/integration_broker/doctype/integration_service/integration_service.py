# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class IntegrationService(Document):
	def validate(self):
		self.install_events()
		parameters = self.get_parameters()
		for d in self.get_controller().parameters:
			if d.reqd and not parameters.get(d.label):
				frappe.throw(_('Parameter {0} is mandatory').format(d.label), title=_('Missing Parameter'))
			
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
		for d in self.parameters:
			parameters[d.label] = d.value
			
		return parameters

	def install_events(self):
		'''Install events for controller'''
		for d in self.get_controller().events:
			if not frappe.db.exists('Integration Event', d.event):
				event = frappe.new_doc('Integration Event')
				event.update(d)
				event.insert()

	def install_fixtures(self):
		pass

	def enable_service(self):
		self.get_controller().enable()

	def setup_events_and_parameters(self):
		self.parameters = []
		for d in self.get_controller().parameters:
			self.parameters.append({'label': d.label})

		self.events = []
		for d in self.get_controller().events:
			self.parameters.append({'event': d.event, 'enabled': d.enabled})

@frappe.whitelist()
def get_events_and_parameters(service):
	controller = get_integration_controller(service, setup=False)
	return {
		'events': controller.events,
		'parameters': controller.parameters
	}
		
def get_integration_controller(service_name, setup=True):
	'''Returns integration controller module from app_name.integrations.{service}'''
	def load_from_app(app, service_name):
		try:
			controller_module = frappe.get_module("{app}.integrations.{service}"
				.format(app=app, service=service_name.strip().lower().replace(' ','_')))
			
			controller = controller_module.Controller(setup=setup)
			
			# make default properites and frappe._dictify
			for key in ('events', 'parameters'):
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
		