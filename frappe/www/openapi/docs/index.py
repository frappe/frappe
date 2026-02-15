import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if not frappe.conf.get("enable_openapi"):
        context.enable_openapi = False
        context.message = (
            "OpenAPI specification is disabled. Please contact your administrator."
        )
    else:
        context.enable_openapi = True
