import frappe
from   frappe.chat.util import filter_dict, safe_json_loads

@frappe.whitelist(allow_guest = True)
def settings(fields = None):
    fields    = safe_json_loads(fields)

    dsettings = frappe.get_single('Website Settings')
    response  = dict(
        socketio         = dict(
            port         = frappe.conf.socketio_port
        ),
        enable           = bool(dsettings.chat_enable),
        enable_from      = dsettings.chat_enable_from,
        enable_to        = dsettings.chat_enable_to,
        room_name        = dsettings.chat_room_name,
        welcome_message  = dsettings.chat_welcome_message,
        operators        = [
            duser.user for duser in dsettings.chat_operators
        ]
    )

    if fields:
        response = filter_dict(response, fields)

    return response

@frappe.whitelist(allow_guest = True)
def token():
    token = frappe.generate_hash()
    return token