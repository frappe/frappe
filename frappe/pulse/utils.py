"""Compatibility shim: keep old `frappe.pulse.utils` imports working."""

from frappe.utils import get_app_version, get_frappe_version

__all__ = ["get_app_version", "get_frappe_version"]
