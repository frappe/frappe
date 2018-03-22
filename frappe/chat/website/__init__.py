import frappe

@frappe.whitelist(allow_guest = True)
def settings():
    dsettings = frappe.get_single('Website Settings')
    response  = dict(
        socketio        = dict(
            port        = frappe.conf.socketio_port
        ),
        enable_chat     = dsettings.chat_enable,
        welcome_message = dsettings.chat_welcome_message,
        operators       = [
            duser.user for duser in dsettings.chat_operators
        ]
    )

    return response