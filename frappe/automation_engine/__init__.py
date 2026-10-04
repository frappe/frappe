# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

# The integration surface apps import. Everything else lives in the submodules.
from frappe.automation_engine.events import emit
from frappe.automation_engine.settings import is_enabled, skip_automations

__all__ = ["emit", "is_enabled", "skip_automations"]
