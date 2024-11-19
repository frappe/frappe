import frappe
from urllib.parse import unquote
from onelogin.saml2.auth import OneLogin_Saml2_Auth

@frappe.whitelist(allow_guest=True)
def saml_login_initiate(provider):
    # Fetch the SAML provider settings
    saml_key = frappe.get_doc('Saml Login Key', provider)
    if not saml_key:
        frappe.throw(_("SAML provider settings not found"))

    # Create the SAML settings dictionary
    saml_settings = {
        "sp": {
            "entityId": saml_key.sp_entity_id,
            "assertionConsumerService": {
                "url": saml_key.acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
        },
        "idp": {
            "entityId": saml_key.audience_uri,
            "singleSignOnService": {
                "url": saml_key.sso_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "x509cert": saml_key.certificate,
        }
    }
    request_data = {
        "http_host": frappe.local.request.host,
        "server_port": frappe.local.request.environ.get("SERVER_PORT"),
        "script_name": frappe.local.request.environ.get("PATH_INFO"),
        "query_string": frappe.local.request.environ.get("QUERY_STRING"),
        "https": "on" if frappe.local.request.scheme == "https" else "off",
    }

    client = OneLogin_Saml2_Auth(request_data, saml_settings)

    redirect_url = client.login()
    redirect_url=unquote(redirect_url)
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = redirect_url

@frappe.whitelist(allow_guest=True)
def saml_acs():
    try:
        frappe.throw("dsasdadsaasdsad")
        # Handle the SAML response
        request_data = {
            "http_host": frappe.local.request.host,
            "server_port": frappe.local.request.environ.get("SERVER_PORT"),
            "script_name": frappe.local.request.environ.get("PATH_INFO"),
            "query_string": frappe.local.request.environ.get("QUERY_STRING"),
            "https": "on" if frappe.local.request.scheme == "https" else "off",
        }

        saml_key = frappe.get_doc("Saml Login Key", "pflgngf22f")
        if not saml_key:
            frappe.respond_as_web_page(_("SAML Login Failed"), _("SAML configuration missing"), http_status_code=500)
            return

        # Create the SAML settings dictionary
        saml_settings = {
            "sp": {
                "entityId": saml_key.sp_entity_id,
                "assertionConsumerService": {
                    "url": saml_key.acs_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                },
            },
            "idp": {
                "entityId": saml_key.audience_uri,
                "singleSignOnService": {
                    "url": saml_key.sso_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                },
                "x509cert": saml_key.certificate,
            }
        }

        client = OneLogin_Saml2_Auth(request_data, saml_settings)
        client.process_response()

        errors = client.get_errors()
        if errors:
            frappe.respond_as_web_page(_("SAML Login Failed"), _("Invalid SAML response: ") + ", ".join(errors), http_status_code=403)
            return

        if not client.is_authenticated():
            frappe.respond_as_web_page(_("SAML Login Failed"), _("User not authenticated"), http_status_code=403)
            return

        # Extract user data
        user_data = client.get_attributes()
        user_email = user_data.get("email", [None])[0]
        if not user_email:
            frappe.respond_as_web_page(_("SAML Login Failed"), _("Email not found in SAML response"), http_status_code=403)
            return

        # Check if the user exists
        user = frappe.db.get_value("User", {"email": user_email})
        if not user:
            frappe.respond_as_web_page(_("SAML Login Failed"), _("User not found"), http_status_code=403)
            return

        # Log the user in
        frappe.local.login_manager.user = user
        frappe.local.login_manager.post_login()
        frappe.db.commit()

        # Redirect to workspace
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = frappe.utils.get_url("/app")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("SAML Login Error"))
        frappe.respond_as_web_page(_("SAML Login Failed"), frappe.get_traceback(), http_status_code=500)