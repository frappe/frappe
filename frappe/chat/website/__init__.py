import frappe

@frappe.whitelist(allow_guest = True)
def settings():
    dsettings = frappe.get_single('Website Settings')
    response  = dict(
        socketio        = dict(
            port        = frappe.conf.socketio_port
        ),
        enable_chat     = bool(dsettings.chat_enable),
        welcome_message = dsettings.chat_welcome_message,
        operators       = [
            duser.user for duser in dsettings.chat_operators
        ]
    )

    return response

@frappe.whitelist(allow_guest = True)
def token():
    token = frappe.generate_hash()
    return token