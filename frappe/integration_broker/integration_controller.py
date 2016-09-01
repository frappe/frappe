# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

from frappe.integration_broker.doctype.integration_service.integration_service import IntegrationService

class IntegrationController(IntegrationService):
	def __init__(self, setup=True):
		'''Load the current controller data if setup is true'''
		if setup:
			super(IntegrationController, self).__init__('Integration Service', self.service_name)
