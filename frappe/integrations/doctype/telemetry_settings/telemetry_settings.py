# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TelemetrySettings(Document):
    def enable_telemetry(self, app):
        app_item = self.get("apps", {"app": app})
        if not app_item:
            app_item = self.append("apps", {"app": app})
        app_item[0].enabled = 1
        self.save(ignore_permissions=True, ignore_mandatory=True)

    def is_tracking_enabled(self, app):
        app_item = self.get("apps", {"app": app})
        return app_item and app_item[0].enabled


