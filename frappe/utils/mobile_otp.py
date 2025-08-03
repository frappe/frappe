# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.twofactor import (
	get_otpsecret_for_, 
	send_token_via_sms,
	get_verification_method
)
from frappe.auth import get_login_attempt_tracker
from frappe.utils import cint
import pyotp


def is_mobile_otp_login_enabled():
	"""Check if mobile OTP login is enabled."""
	return (
		cint(frappe.get_system_settings("allow_login_using_mobile_number"))
		and cint(frappe.get_system_settings("allow_mobile_login_with_otp"))
	)


def validate_mobile_otp_prerequisites():
	"""Validate that all prerequisites for mobile OTP login are met."""
	if not cint(frappe.get_system_settings("allow_login_using_mobile_number")):
		frappe.throw(_("Mobile login is not enabled."), frappe.AuthenticationError)
	
	if not cint(frappe.get_system_settings("allow_mobile_login_with_otp")):
		frappe.throw(_("Mobile OTP login is not enabled."), frappe.AuthenticationError)
	
	# Check SMS settings using existing validation
	sms_gateway_url = frappe.db.get_single_value("SMS Settings", "sms_gateway_url")
	if not sms_gateway_url:
		frappe.throw(
			_("SMS Settings are not configured. Please contact administrator."), 
			frappe.AuthenticationError
		)


def find_user_by_mobile(mobile_no):
	"""Find user by mobile number with proper validation."""
	if not mobile_no:
		frappe.throw(_("Mobile number is required."), frappe.ValidationError)
	
	# Use existing user lookup logic
	user = frappe.db.get_value(
		"User", 
		{"mobile_no": mobile_no, "enabled": 1}, 
		["name", "mobile_no"], 
		as_dict=True
	)
	
	if not user:
		# Track failed attempts using existing tracker
		ip_tracker = get_login_attempt_tracker(frappe.local.request_ip, raise_locked_exception=False)
		if ip_tracker:
			ip_tracker.add_failure_attempt()
		frappe.throw(_("No user found with this mobile number."), frappe.AuthenticationError)
	
	return user


def generate_mobile_otp(user):
	"""Generate OTP for mobile login using existing secure methods."""
	# Use existing OTP secret generation (encrypted storage)
	otp_secret = get_otpsecret_for_(user)
	
	# Generate token using existing method
	token = int(pyotp.TOTP(otp_secret).now())
	
	return token, otp_secret


def cache_mobile_otp_data(user, token, otp_secret, tmp_id):
	"""Cache mobile OTP data without requiring password."""
	verification_method = get_verification_method()

	pipeline = frappe.cache.pipeline()

	# Set increased expiry time for SMS
	if verification_method == "SMS":
		expiry_time = frappe.flags.token_expiry or 300
		pipeline.set(tmp_id + "_token", token, expiry_time)
	else:
		expiry_time = frappe.flags.otp_expiry or 180
	
	# Ensure all values are strings (not bytes)
	user = str(user) if user else ""
	otp_secret = str(otp_secret) if otp_secret else ""
	
	# Cache user and OTP secret without password
	for k, v in {"_usr": user, "_otp_secret": otp_secret}.items():
		pipeline.set(f"{tmp_id}{k}", v, expiry_time)
	pipeline.execute()


def send_mobile_login_otp(user, mobile_no):
	"""Send OTP for mobile login using existing SMS infrastructure."""
	validate_mobile_otp_prerequisites()
	
	# Check rate limiting using existing tracker
	user_tracker = get_login_attempt_tracker(user, raise_locked_exception=True)
	
	# Generate OTP using existing secure method
	token, otp_secret = generate_mobile_otp(user)
	
	# Generate session ID
	tmp_id = frappe.generate_hash(length=8)
	
	# Cache OTP data using mobile-specific method (no password required)
	cache_mobile_otp_data(user, token, otp_secret, tmp_id)
	
	# Hook support for custom SMS sender
	hook_methods = frappe.get_hooks("mobile_otp_sms_sender")
	if hook_methods:
		status = frappe.get_attr(hook_methods[-1])(otp_secret, token=token, phone_no=mobile_no)
	else:
		status = send_token_via_sms(otp_secret, token=token, phone_no=mobile_no)

	if not status:
		frappe.throw(_("Failed to send OTP. Please try again."), frappe.AuthenticationError)
	
	# Format mobile number for display (security)
	masked_mobile = mobile_no[:4] + "******" + mobile_no[-3:] if len(mobile_no) > 7 else "******"
	
	return {
		"message": _("OTP sent successfully"),
		"tmp_id": tmp_id,
		"mobile_no": masked_mobile
	}


def verify_mobile_login_otp(otp, tmp_id):
	"""Verify OTP for mobile login using existing verification logic."""
	if not otp or not tmp_id:
		frappe.throw(_("OTP and session ID are required."), frappe.ValidationError)
	
	# Get cached data using existing method
	user = frappe.cache.get(tmp_id + "_usr")
	token = frappe.cache.get(tmp_id + "_token")
	otp_secret = frappe.cache.get(tmp_id + "_otp_secret")
	
	if not user or not otp_secret:
		frappe.throw(_("Login session expired. Please try again."), frappe.AuthenticationError)
	
	# Decode bytes to string if necessary
	if isinstance(user, bytes):
		user = user.decode('utf-8')
	if isinstance(otp_secret, bytes):
		otp_secret = otp_secret.decode('utf-8')
	
	# Get tracker for user
	user_tracker = get_login_attempt_tracker(user, raise_locked_exception=False)
	
	# Verify OTP using existing HOTP verification (same as 2FA)
	hotp = pyotp.HOTP(otp_secret)
	if token and hotp.verify(otp, int(token)):
		# Success - clear cache and add success attempt
		frappe.cache.delete(tmp_id + "_token")
		frappe.cache.delete(tmp_id + "_usr") 
		frappe.cache.delete(tmp_id + "_otp_secret")
		
		if user_tracker:
			user_tracker.add_success_attempt()
		
		return user
	else:
		# Failed - add failure attempt
		if user_tracker:
			user_tracker.add_failure_attempt()
		frappe.throw(_("Invalid OTP. Please try again."), frappe.AuthenticationError)


def cleanup_expired_mobile_otp_sessions():
	"""Cleanup expired mobile OTP sessions - handled by cache TTL automatically."""
	# No need for manual cleanup as cache entries have TTL
	pass 