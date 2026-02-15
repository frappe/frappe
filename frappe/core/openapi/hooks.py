# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.core.openapi.generator import generate_specification


def on_site_migrate():
    """Generate OpenAPI specification after site migration."""
    try:
        frappe.logger().info("Generating OpenAPI specification after migration")
        generate_specification()
        frappe.logger().info("OpenAPI specification generated successfully")
    except Exception as e:
        frappe.logger().error(f"Failed to generate OpenAPI specification: {e}")
        frappe.log_error(
            title="OpenAPI Generation Failed",
            message=str(frappe.get_traceback()),
        )
