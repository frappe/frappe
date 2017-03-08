# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class IntegrationService(Document):
	pass

@frappe.whitelist()
def get_integration_services():
	services = [""]
	for app in frappe.get_installed_apps():
		services.extend(frappe.get_hooks("integration_services", app_name = app))

	return services

def get_integration_service_events():
	'''Get scheduler events for enabled integrations'''
	events = {}
	for service in frappe.get_all("Integration Service", filters={"enabled": 1},
		fields=["name"]):
		controller = get_integration_controller(service.name)

		if hasattr(controller, "scheduler_events"):
			for key, handlers in controller.scheduler_events.items():
				events.setdefault(key, []).extend(handlers)

	return events
