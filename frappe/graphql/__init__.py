import frappe

from frappe import _
from frappe.api import validate_oauth
from frappe.api import validate_auth_via_api_keys
from frappe.handler import get_attr
from frappe.utils.response import build_response


def handle():
    validate_oauth()
    validate_auth_via_api_keys()

    parts = frappe.request.path[1:].split('/')

    if len(parts) > 1:
        frappe.DoesNotExistError

    return execute()


def execute():
    if frappe.session['user'] == 'Guest':
        frappe.msgprint(_('Not permitted'))
        raise frappe.PermissionError(
            'Guest not allowed'
        )

    # execute command directly will cause error
    # RuntimeError("no object bound to %s" % self.__name__)
    method = get_attr('frappe.graphql.schema.execute')
    result = frappe.call(method)

    frappe.response['data'] = result.data
    if result.errors:
        error_response = []
        for e in result.errors:

            error_locations = []
            for loc in e.locations:
                error_locations.append({
                    'line': loc.line,
                    'column': loc.column,
                })

            error_response.append(
                {
                    'message': e.message,
                    'locations': error_locations,
                    'path': e.path,
                }
            )
        frappe.response['errors'] = error_response

    return build_response('json')
