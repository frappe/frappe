# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
import frappe.utils
from frappe import _
from frappe.auth import LoginManager
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, get_url
from frappe.utils.data import escape_html
from frappe.utils.html_utils import get_icon_html
from frappe.utils.jinja import guess_is_path
from frappe.utils.oauth import get_oauth2_authorize_url, get_oauth_keys, redirect_post_login
from frappe.utils.password import get_decrypted_password
from frappe.website.utils import get_home_page

no_cache = True


def get_context(context):
    redirect_to = frappe.local.request.args.get("redirect-to")
    if cint(frappe.get_system_settings("login_using_mobile_number_with_otp")):
        context["allow_login_using_mobile_number"] = True

    # if cint(frappe.get_system_settings("login_ui_page")):
    #     context["allow_login_ui_page"] = True

    if frappe.session.user != "Guest":
        if not redirect_to:
            if frappe.session.data.user_type == "Website User":
                redirect_to = get_home_page()
            else:
                redirect_to = "/app"

        if redirect_to != "login":
            frappe.local.flags.redirect_location = redirect_to
            raise frappe.Redirect
    login_image = frappe.get_single("Login Image")
    if login_image and login_image.image_url:
        # Pass the image URL to the context
        context["login_image_url"] = frappe.utils.get_url(login_image.image_url)
    context.no_header = True
    context.for_test = "login.html"
    context["title"] = "Login"
    context["hide_login"] = True  # don't show login link on the login page again.
    context["provider_logins"] = []
    context["disable_signup"] = cint(frappe.get_website_settings("disable_signup"))
    context["disable_user_pass_login"] = cint(frappe.get_system_settings("disable_user_pass_login"))
    context["logo"] = frappe.get_website_settings("app_logo") or frappe.get_hooks("app_logo_url")[-1]
    context["app_name"] = (
        frappe.get_website_settings("app_name") or frappe.get_system_settings("app_name") or _("Frappe")
    )

    signup_form_template = frappe.get_hooks("signup_form_template")
    if signup_form_template and len(signup_form_template):
        path = signup_form_template[-1]
        if not guess_is_path(path):
            path = frappe.get_attr(signup_form_template[-1])()
    else:
        path = "frappe/templates/signup.html"

    if path:
        context["signup_form_template"] = frappe.get_template(path).render()

    providers = frappe.get_all(
        "Social Login Key",
        filters={"enable_social_login": 1},
        fields=["name", "client_id", "base_url", "provider_name", "icon"],
        order_by="name",
    )

    for provider in providers:
        client_secret = get_decrypted_password("Social Login Key", provider.name, "client_secret")
        if not client_secret:
            continue

        icon = None
        if provider.icon:
            if provider.provider_name == "Custom":
                icon = get_icon_html(provider.icon, small=True)
            else:
                icon = f"<img src={escape_html(provider.icon)!r} alt={escape_html(provider.provider_name)!r}>"

        if provider.client_id and provider.base_url and get_oauth_keys(provider.name):
            context.provider_logins.append(
                {
                    "name": provider.name,
                    "provider_name": provider.provider_name,
                    "auth_url": get_oauth2_authorize_url(provider.name, redirect_to),
                    "icon": icon,
                }
            )
            context["social_login"] = True

    if cint(frappe.db.get_value("LDAP Settings", "LDAP Settings", "enabled")):
        from frappe.integrations.doctype.ldap_settings.ldap_settings import LDAPSettings

        context["ldap_settings"] = LDAPSettings.get_ldap_client_settings()

    login_label = [_("Email")]

    if frappe.utils.cint(frappe.get_system_settings("allow_login_using_mobile_number")):
        login_label.append(_("Mobile"))

    if frappe.utils.cint(frappe.get_system_settings("allow_login_using_user_name")):
        login_label.append(_("Username"))

    context["login_label"] = f" {_('or')} ".join(login_label)

    context["login_with_email_link"] = frappe.get_system_settings("login_with_email_link")

    return context



@frappe.whitelist(allow_guest=True)
def login_via_token(login_token: str):
	sid = frappe.cache.get_value(f"login_token:{login_token}", expires=True)
	if not sid:
		frappe.respond_as_web_page(_("Invalid Request"), _("Invalid Login Token"), http_status_code=417)
		return

	frappe.local.form_dict.sid = sid
	frappe.local.login_manager = LoginManager()

	redirect_post_login(
		desk_user=frappe.db.get_value("User", frappe.session.user, "user_type") == "System User"
	)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=60 * 60)
def send_login_link(email: str):

	if not frappe.get_system_settings("login_with_email_link"):
		return

	expiry = frappe.get_system_settings("login_with_email_link_expiry") or 10
	link = _generate_temporary_login_link(email, expiry)

	app_name = (
		frappe.get_website_settings("app_name") or frappe.get_system_settings("app_name") or _("Frappe")
	)

	subject = _("Login To {0}").format(app_name)

	frappe.sendmail(
		subject=subject,
		recipients=email,
		template="login_with_email_link",
		args={"link": link, "minutes": expiry, "app_name": app_name},
		now=True,
	)


def _generate_temporary_login_link(email: str, expiry: int):
	assert isinstance(email, str)

	if not frappe.db.exists("User", email):
		frappe.throw(
			_("User with email address {0} does not exist").format(email), frappe.DoesNotExistError
		)
	key = frappe.generate_hash()
	frappe.cache.set_value(f"one_time_login_key:{key}", email, expires_in_sec=expiry * 60)

	return get_url(f"/api/method/frappe.www.login.login_via_key?key={key}")


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=5, seconds=60 * 60)
def login_via_key(key: str):
	cache_key = f"one_time_login_key:{key}"
	email = frappe.cache.get_value(cache_key)

	if email:
		frappe.cache.delete_value(cache_key)

		frappe.local.login_manager.login_as(email)

		redirect_post_login(
			desk_user=frappe.db.get_value("User", frappe.session.user, "user_type") == "System User"
		)
	else:
		frappe.respond_as_web_page(
			_("Not Permitted"),
			_("The link you trying to login is invalid or expired."),
			http_status_code=403,
			indicator_color="red",
		)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=60 * 60)
def login_via_mobile_number(mobile_number: str):
    # Add logic to send OTP to the provided mobile number and validate it
    # ... (implementation needed for sending OTP and validation)
    # If the mobile number is validated, log in the user
    frappe.local.login_manager.login_as(email)  # replace 'email' with the actual email of the user

    redirect_post_login(
        desk_user=frappe.db.get_value("User", frappe.session.user, "user_type") == "System User"
    )






@frappe.whitelist(allow_guest=True)
def check_mobile(mobile):
    user = frappe.get_value("User", {"mobile_no": mobile}, "name")
    if user:
        # Display success message in Frappe
        # frappe.msgprint(_("Mobile number found."), title=_("Success"))
        return {"status": "success", "user_mobile": mobile}
    else:
        # Display error message in Frappe
        frappe.msgprint(_("Mobile number not found."), title=_("Error"))
        return {"status": "error"}

@frappe.whitelist(allow_guest=True)
def send_mobile_otp(mobile):
    # Implement your logic to generate and send OTP to the provided mobile number
    # You may use an SMS gateway or any other method for sending OTP

    # For example, you can use a hypothetical function send_otp_to_mobile
    otp_sent = send_otp_to_mobile(mobile)

    if otp_sent:
        # Display success message in Frappe
        # frappe.msgprint(_("Verification code sent to mobile. Please enter the code."), title=_("Success"))
        # Return a response indicating success and any additional information
        return {"status": "success", "setup": True, "prompt": _("Verification code sent to mobile. Please enter the code.")}
    else:
        # Log or handle the error
        frappe.log_error(_("Failed to send OTP to mobile"), title="Mobile OTP Error")
        # Display error message in Frappe
        frappe.msgprint(_("Failed to send OTP to mobile. Please try again."), title=_("Error"))
        # Return an error message in the response
        return {"status": "error", "message": _("Failed to send OTP to mobile")}

import requests
from frappe import _

@frappe.whitelist(allow_guest=True)
def send_otp_to_mobile(mobile):
    # Generate a random OTP (you may use a more secure method)
    otp = generate_random_otp()

    # Message body for your API
    message_body = f"Your verification code is: {otp}"

    # URL for sending OTP via your API
    url = "https://wts.vision360solutions.co.in/api/sendText"

    # Parameters for the API request
    params = {
        "token": "609bc2d1392a635870527076",
        "phone": f"91{mobile}",
        "message": message_body,
    }

    try:
        # Send the OTP via your API
        response = requests.post(url, params=params)
        response.raise_for_status()  # Raise an error for HTTP errors (status codes other than 2xx)
        response_data = response.json()

        # Check the response for success
        if response_data.get("status") == "success":
            # Display success message in Frappe
            # frappe.msgprint(_("OTP sent successfully"), title=_("Success"))

            # Store the OTP for the user
            store_otp_for_user(mobile, otp)

            return True
        else:
            # Log or handle the error
            frappe.log_error(_("Failed to send OTP via the API"), title="API Error", exception=response_data.get("error"))
            # Display error message in Frappe
            frappe.msgprint(_("Failed to send OTP. Please try again."), title=_("Error"))
            return False

    except Exception as e:
        # Log the error or handle it appropriately
        frappe.log_error(_("Failed to send OTP via the API"), title="API Error", exception=e)
        # Display error message in Frappe
        frappe.msgprint(_("Failed to send OTP. Please try again."), title=_("Error"))
        return False

from datetime import datetime 

@frappe.whitelist(allow_guest=True)
def store_otp_for_user(mobile, otp):
    try:
        # Store the OTP for the user in the database (replace with your logic)
        # You might want to use the User doctype or create a separate OTP doctype
        user1 = frappe.get_all("User", filters={"mobile_no": mobile})
        user = frappe.get_doc("User", user1[0].name)

        if user:
            # Update or set the OTP field in the User doctype
            user.otp_secret = otp
            user.otp_created_time = datetime.now()
            user.save(ignore_permissions=True)  # Add ignore_permissions parameter

            # frappe.msgprint(_("OTP stored successfully"), title=_("Success"))
        else:
            frappe.msgprint(_("User not found for mobile number: {mobile}"), title=_("Error"))

    except Exception as e:
        # Log the error and display a message
        frappe.log_error(_("Failed to store OTP for user"), title="Error", exception=e)
        frappe.msgprint(_("Failed to store OTP. Please try again."), title=_("Error"))

def generate_random_otp():
    # Implement your logic to generate a random OTP
    # This is a simple example, and you may use a more secure method
    import random
    return str(random.randint(1000, 9999))



from frappe import auth

from frappe import _

@frappe.whitelist(allow_guest=True)
def verify_mobile_otp(mobile, entered_otp):
    user = frappe.get_value("User", {"mobile_no": mobile}, "name")

    if not user:
        frappe.msgprint(_("Mobile number not found."), title=_("Error"))
        return {"status": "error", "message": _("Mobile number not found.")}

    user_otp = frappe.get_all(
        "User",
        filters={"mobile_no": mobile},
        fields=["name", "otp_secret", "email", "new_password"],
        limit=1,
    )

    if not user_otp:
        frappe.msgprint(_("Invalid OTP. Please try again."), title=_("Verification Failed"))
        return {"status": "error", "message": _("Invalid OTP.")}

    user_name = user_otp[0].name
    user_mail = user_otp[0].email

    if user_otp[0].otp_secret == entered_otp:
        # Manually set the user session
        frappe.local.login_manager = frappe.auth.LoginManager()
        frappe.local.login_manager.user = user_name
        frappe.local.login_manager.post_login()
        
        # frappe.msgprint(_("Login successful. Welcome, {0}! Please Wait....").format(user_mail), title=_("Success"))

        return {"status": "success"}

    else:
        frappe.msgprint(_("Invalid OTP. Please try again."), title=_("Verification Failed"))
        return {"status": "error", "message": _("Invalid OTP.")}


@frappe.whitelist(allow_guest=True)
def delete_mobile_otp(mobile):
    try:
        # Fetch user based on mobile number
        user = frappe.get_value("User", {"mobile_no": mobile}, "name")

        if user:
            # Update the user to clear the otp_secret field
            frappe.db.set_value("User", user, "otp_secret", "")
            # frappe.msgprint(_("OTP secret cleared successfully for user {0}").format(user))
            return {"status": "success"}
        else:
            frappe.msgprint(_("User not found for the provided mobile number"), raise_exception=True)
            return {"status": "error", "message": "User not found"}

    except Exception as e:
        frappe.msgprint(_("Error clearing OTP secret: {0}").format(str(e)), raise_exception=True)
        return {"status": "error", "message": str(e)}





import frappe
from datetime import datetime, timedelta

@frappe.whitelist()
def delete_expired_otp_secrets():
    # Fetch all users
    users = frappe.get_all("User", filters={}, fields=["name", "otp_secret", "otp_created_time"])

    # Get current date and time
    current_datetime = datetime.now()

    # Iterate through users
    for user in users:
        otp_created_time = user.get("otp_created_time")

        # Check if otp_created_time is not None
        if otp_created_time:
            # Ensure otp_created_time is a string
            otp_created_time_str = str(otp_created_time)

            try:
                # Convert string to datetime
                otp_created_datetime = datetime.strptime(otp_created_time_str, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                # Handle the case where fractional seconds are not present
                otp_created_datetime = datetime.strptime(otp_created_time_str, "%Y-%m-%d %H:%M:%S")

            # Calculate the time difference
            time_difference = current_datetime - otp_created_datetime

            # Print for debugging
            # print(f"Current Datetime: {current_datetime}")
            # print(f"OTP Created Datetime: {otp_created_datetime}")
            # print(f"Time Difference (seconds): {time_difference.total_seconds()}")

            # Check if the time difference is greater than or equal to 5 minutes
            if time_difference.total_seconds() >= 300:  # 5 minutes in seconds
                # Delete the otp_secret
                frappe.db.set_value("User", user.get("name"), "otp_secret", None)
            else:
                # Provide an alert or log the information
                print(f"Alert: OTP for user {user.get('name')} is still valid.")
