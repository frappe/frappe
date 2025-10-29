# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
from base64 import b32encode, b64encode
from io import BytesIO

import pyotp

import frappe
import frappe.defaults
from frappe import _
from frappe.permissions import ALL_USER_ROLE
from frappe.utils import cint, get_datetime, get_url, time_diff_in_seconds
from frappe.utils.background_jobs import enqueue
from frappe.utils.password import decrypt, encrypt

PARENT_FOR_DEFAULTS = "__2fa"


def get_default(key):
	return frappe.db.get_default(key, parent=PARENT_FOR_DEFAULTS)


def set_default(key, value):
	frappe.db.set_default(key, value, parent=PARENT_FOR_DEFAULTS)


def clear_default(key):
	frappe.defaults.clear_default(key, parent=PARENT_FOR_DEFAULTS)


class ExpiredLoginException(Exception):
	pass


def toggle_two_factor_auth(state, roles=None):
	"""Enable or disable 2FA in site_config and roles"""
	for role in roles or []:
		role = frappe.get_doc("Role", {"role_name": role})
		role.two_factor_auth = cint(state)
		role.save(ignore_permissions=True)


def two_factor_is_enabled(user=None):
	"""Return True if 2FA is enabled."""
	enabled = cint(frappe.get_system_settings("enable_two_factor_auth"))
	if enabled:
		bypass_two_factor_auth = cint(frappe.get_system_settings("bypass_2fa_for_retricted_ip_users"))
		if bypass_two_factor_auth and user:
			user_doc = frappe.get_doc("User", user)
			restrict_ip_list = (
				user_doc.get_restricted_ip_list()
			)  # can be None or one or more than one ip address
			if restrict_ip_list and frappe.local.request_ip:
				for ip in restrict_ip_list:
					if frappe.local.request_ip.startswith(ip):
						enabled = False
						break

	if not user or not enabled:
		return enabled
	return two_factor_is_enabled_for_(user)


def should_run_2fa(user):
	"""Check if 2fa should run."""
	return two_factor_is_enabled(user=user)


def get_cached_user_pass():
	"""Get user and password if set."""
	user = pwd = None
	tmp_id = frappe.form_dict.get("tmp_id")
	if tmp_id:
		user = frappe.safe_decode(frappe.cache.get(tmp_id + "_usr"))
		pwd = frappe.safe_decode(frappe.cache.get(tmp_id + "_pwd"))
	return (user, pwd)


def authenticate_for_2factor(user):
	"""Authenticate two factor for enabled user before login."""
	if frappe.form_dict.get("otp"):
		return
	otp_secret = get_otpsecret_for_(user)
	token = int(pyotp.TOTP(otp_secret).now())
	tmp_id = frappe.generate_hash(length=8)
	cache_2fa_data(user, token, otp_secret, tmp_id)
	verification_obj = get_verification_obj(user, token, otp_secret)
	# Save data in local
	frappe.local.response["verification"] = verification_obj
	frappe.local.response["tmp_id"] = tmp_id


def cache_2fa_data(user, token, otp_secret, tmp_id):
	"""Cache and set expiry for data."""
	pwd = frappe.form_dict.get("pwd")
	verification_method = get_verification_method()

	pipeline = frappe.cache.pipeline()

	# set increased expiry time for SMS and Email
	if verification_method in ["SMS", "Email"]:
		expiry_time = frappe.flags.token_expiry or 300
		pipeline.set(tmp_id + "_token", token, expiry_time)
	else:
		expiry_time = frappe.flags.otp_expiry or 180
	for k, v in {"_usr": user, "_pwd": pwd, "_otp_secret": otp_secret}.items():
		pipeline.set(f"{tmp_id}{k}", v, expiry_time)
	pipeline.execute()


def two_factor_is_enabled_for_(user):
	"""Check if 2factor is enabled for user."""
	if user == "Administrator":
		return False

	if isinstance(user, str):
		user = frappe.get_doc("User", user)
	roles = [d.role for d in user.roles or []] + [ALL_USER_ROLE]

	role_doctype = frappe.qb.DocType("Role")
	no_of_users = frappe.db.count(
		role_doctype,
		filters=((role_doctype.two_factor_auth == 1) & (role_doctype.name.isin(roles))),
	)

	if int(no_of_users) > 0:
		return True

	return False


def get_otpsecret_for_(user):
	"""Set OTP Secret for user even if not set."""
	if otp_secret := get_default(user + "_otpsecret"):
		return decrypt(otp_secret, key=f"{user}.otpsecret")

	otp_secret = b32encode(os.urandom(10)).decode("utf-8")
	set_default(user + "_otpsecret", encrypt(otp_secret))
	frappe.db.commit()

	return otp_secret


def get_verification_method():
	return frappe.get_system_settings("two_factor_method")


def confirm_otp_token(login_manager, otp=None, tmp_id=None):
	"""Confirm otp matches."""
	from frappe.auth import get_login_attempt_tracker

	if not otp:
		otp = frappe.form_dict.get("otp")
	if not otp:
		if two_factor_is_enabled_for_(login_manager.user):
			return False
		return True
	if not tmp_id:
		tmp_id = frappe.form_dict.get("tmp_id")
	hotp_token = frappe.cache.get(tmp_id + "_token")
	otp_secret = frappe.cache.get(tmp_id + "_otp_secret")
	if not otp_secret:
		raise ExpiredLoginException(_("Login session expired, refresh page to retry"))

	tracker = get_login_attempt_tracker(login_manager.user)

	hotp = pyotp.HOTP(otp_secret)
	if hotp_token:
		if hotp.verify(otp, int(hotp_token)):
			frappe.cache.delete(tmp_id + "_token")
			tracker.add_success_attempt()
			return True
		else:
			tracker.add_failure_attempt()
			login_manager.fail(_("Incorrect Verification code"), login_manager.user)

	totp = pyotp.TOTP(otp_secret)
	if totp.verify(otp):
		# show qr code only once
		if not get_default(login_manager.user + "_otplogin"):
			set_default(login_manager.user + "_otplogin", 1)
			delete_qrimage(login_manager.user)
		tracker.add_success_attempt()
		return True
	else:
		tracker.add_failure_attempt()
		login_manager.fail(_("Incorrect Verification code"), login_manager.user)


def get_verification_obj(user, token, otp_secret):
	otp_issuer = frappe.get_system_settings("otp_issuer_name")
	verification_method = get_verification_method()
	verification_obj = None
	if verification_method == "SMS":
		verification_obj = process_2fa_for_sms(user, token, otp_secret)
	elif verification_method == "OTP App":
		# check if this if the first time that the user is trying to login. If so, send an email
		if not get_default(user + "_otplogin"):
			verification_obj = process_2fa_for_email(user, token, otp_secret, otp_issuer, method="OTP App")
		else:
			verification_obj = process_2fa_for_otp_app(user, otp_secret, otp_issuer)
	elif verification_method == "Email":
		verification_obj = process_2fa_for_email(user, token, otp_secret, otp_issuer)
	return verification_obj


def process_2fa_for_sms(user, token, otp_secret):
	"""Process sms method for 2fa."""
	phone = frappe.db.get_value("User", user, ["phone", "mobile_no"], as_dict=1)
	phone = phone.mobile_no or phone.phone
	status = send_token_via_sms(otp_secret, token=token, phone_no=phone)
	return {
		"token_delivery": status,
		"prompt": status and "Enter verification code sent to {}".format(phone[:4] + "******" + phone[-3:]),
		"method": "SMS",
		"setup": status,
	}


def process_2fa_for_otp_app(user, otp_secret, otp_issuer):
	"""Process OTP App method for 2fa."""
	if get_default(user + "_otplogin"):
		otp_setup_completed = True
	else:
		otp_setup_completed = False

	return {"method": "OTP App", "setup": otp_setup_completed}


def process_2fa_for_email(user, token, otp_secret, otp_issuer, method="Email"):
	"""Process Email method for 2fa."""
	subject = None
	message = None
	status = True
	prompt = ""
	if method == "OTP App" and not get_default(user + "_otplogin"):
		"""Sending one-time email for OTP App"""
		totp_uri = pyotp.TOTP(otp_secret).provisioning_uri(user, issuer_name=otp_issuer)
		qrcode_link = get_link_for_qrcode(user, totp_uri)
		message = get_email_body_for_qr_code({"qrcode_link": qrcode_link})
		subject = get_email_subject_for_qr_code({"qrcode_link": qrcode_link})
		prompt = _(
			"Please check your registered email address for instructions on how to proceed. Do not close this window as you will have to return to it."
		)
	else:
		"""Sending email verification"""
		prompt = _("Verification code has been sent to your registered email address.")
	status = send_token_via_email(user, token, otp_secret, otp_issuer, subject=subject, message=message)
	return {
		"token_delivery": status,
		"prompt": status and prompt,
		"method": "Email",
		"setup": status,
	}


def get_email_subject_for_2fa(kwargs_dict):
	"""Get email subject for 2fa."""
	subject_template = _("Login Verification Code from {}").format(
		frappe.get_system_settings("otp_issuer_name")
	)
	return frappe.render_template(subject_template, kwargs_dict)


def get_email_body_for_2fa(kwargs_dict):
	"""Get email body for 2fa."""
	body_template = """
		Enter this code to complete your login:
		<br><br>
		<b style="font-size: 18px;">{{ otp }}</b>
	"""
	return frappe.render_template(body_template, kwargs_dict)


def get_email_subject_for_qr_code(kwargs_dict):
	"""Get QRCode email subject."""
	subject_template = _("One Time Password (OTP) Registration Code from {}").format(
		frappe.get_system_settings("otp_issuer_name")
	)
	return frappe.render_template(subject_template, kwargs_dict)


def get_email_body_for_qr_code(kwargs_dict):
	"""Get QRCode email body."""
	body_template = _(
		"Please click on the following link and follow the instructions on the page. {0}"
	).format("<br><br> <a href='{{qrcode_link}}'>{{qrcode_link}}</a>")
	return frappe.render_template(body_template, kwargs_dict)


def get_link_for_qrcode(user, totp_uri):
	"""Get link to temporary page showing QRCode."""
	key = frappe.generate_hash(length=20)
	key_user = f"{key}_user"
	key_uri = f"{key}_uri"
	lifespan = int(frappe.get_system_settings("lifespan_qrcode_image")) or 240
	frappe.cache.set_value(key_uri, totp_uri, expires_in_sec=lifespan)
	frappe.cache.set_value(key_user, user, expires_in_sec=lifespan)
	return get_url(f"/qrcode?k={key}")


def send_token_via_sms(otpsecret, token=None, phone_no=None):
	"""Send token as sms to user."""

	send_token_hook_methods = frappe.get_hooks("send_token_via_sms")
	if send_token_hook_methods:
		return frappe.get_attr(send_token_hook_methods[-1])(otpsecret, token, phone_no)

	try:
		from frappe.core.doctype.sms_settings.sms_settings import send_request
	except Exception:
		return False

	if not phone_no:
		return False

	ss = frappe.get_doc("SMS Settings", "SMS Settings")
	if not ss.sms_gateway_url:
		return False

	hotp = pyotp.HOTP(otpsecret)
	args = {ss.message_parameter: f"Your verification code is {hotp.at(int(token))}"}

	for d in ss.get("parameters"):
		args[d.parameter] = d.value

	args[ss.receiver_parameter] = phone_no

	sms_args = {"params": args, "gateway_url": ss.sms_gateway_url, "use_post": ss.use_post}
	enqueue(
		method=send_request,
		queue="short",
		timeout=300,
		event=None,
		is_async=True,
		job_name=None,
		now=False,
		**sms_args,
	)
	return True


def send_token_via_email(user, token, otp_secret, otp_issuer, subject=None, message=None):
	"""Send token to user as email."""
	user_email = frappe.db.get_value("User", user, "email")
	if not user_email:
		return False
	hotp = pyotp.HOTP(otp_secret)
	otp = hotp.at(int(token))
	template_args = {"otp": otp, "otp_issuer": otp_issuer}

	frappe.sendmail(
		recipients=user_email,
		subject=subject or get_email_subject_for_2fa(template_args),
		message=message or get_email_body_for_2fa(template_args),
		header=[_("Verification Code"), "blue"],
		delayed=False,
		retry=3,
	)
	return True


def get_qr_svg_code(totp_uri):
	"""Get SVG code to display Qrcode for OTP."""
	from pyqrcode import create as qrcreate

	url = qrcreate(totp_uri)
	svg = ""
	stream = BytesIO()
	try:
		url.svg(stream, scale=4, background="#eee", module_color="#222")
		svg = stream.getvalue().decode().replace("\n", "")
		svg = b64encode(svg.encode())
	finally:
		stream.close()
	return svg


def create_barcode_folder():
	"""Get Barcodes folder."""
	folder_name = "Barcodes"
	folder = frappe.db.exists("File", {"file_name": folder_name})
	if folder:
		return folder
	folder = frappe.get_doc({"doctype": "File", "file_name": folder_name, "is_folder": 1, "folder": "Home"})
	folder.insert(ignore_permissions=True)
	return folder.name


def delete_qrimage(user, check_expiry=False):
	"""Delete Qrimage when user logs in."""
	user_barcodes = frappe.get_all(
		"File", {"attached_to_doctype": "User", "attached_to_name": user, "folder": "Home/Barcodes"}
	)

	for barcode in user_barcodes:
		if check_expiry and not should_remove_barcode_image(barcode):
			continue
		barcode = frappe.get_doc("File", barcode.name)
		frappe.delete_doc("File", barcode.name, ignore_permissions=True)


def delete_all_barcodes_for_users():
	"""Task to delete all barcodes for user."""

	users = frappe.get_all("User", {"enabled": 1})
	for user in users:
		if not two_factor_is_enabled(user=user.name):
			continue
		delete_qrimage(user.name, check_expiry=True)


def should_remove_barcode_image(barcode):
	"""Check if it's time to delete barcode image from server."""
	if isinstance(barcode, str):
		barcode = frappe.get_doc("File", barcode)
	lifespan = frappe.get_system_settings("lifespan_qrcode_image") or 240
	if time_diff_in_seconds(get_datetime(), barcode.creation) > int(lifespan):
		return True
	return False


def disable():
	frappe.db.set_single_value("System Settings", "enable_two_factor_auth", 0)


@frappe.whitelist()
def reset_otp_secret(user: str):
	if frappe.session.user != user:
		frappe.only_for("System Manager", message=True)

	settings = frappe.get_cached_doc("System Settings")

	if not settings.enable_two_factor_auth:
		frappe.throw(
			_("You have to enable Two Factor Auth from System Settings."),
			title=_("Enable Two Factor Auth"),
		)

	otp_issuer = settings.otp_issuer_name or "Frappe Framework"
	user_email = frappe.get_cached_value("User", user, "email")

	clear_default(user + "_otplogin")
	clear_default(user + "_otpsecret")

	email_args = {
		"recipients": user_email,
		"sender": None,
		"subject": _("OTP Secret Reset - {0}").format(otp_issuer),
		"message": _(
			"<p>Your OTP secret on {0} has been reset. If you did not perform this reset and did not request it, please contact your System Administrator immediately.</p>"
		).format(otp_issuer),
		"delayed": False,
		"retry": 3,
	}

	enqueue(
		method=frappe.sendmail,
		queue="short",
		timeout=300,
		event=None,
		is_async=True,
		job_name=None,
		now=False,
		**email_args,
	)

	frappe.msgprint(_("OTP Secret has been reset. Re-registration will be required on next login."))
