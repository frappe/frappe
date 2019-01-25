# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
import pyotp, os
from frappe.utils.background_jobs import enqueue
from jinja2 import Template
from pyqrcode import create as qrcreate
from six import BytesIO
from base64 import b64encode, b32encode
from frappe.utils import get_url, get_datetime, time_diff_in_seconds, cint
from six import iteritems, string_types

class ExpiredLoginException(Exception): pass

def toggle_two_factor_auth(state, roles=[]):
	'''Enable or disable 2FA in site_config and roles'''
	for role in roles:
		role = frappe.get_doc('Role', {'role_name': role})
		role.two_factor_auth = cint(state)
		role.save(ignore_permissions=True)

def two_factor_is_enabled(user=None):
	'''Returns True if 2FA is enabled.'''
	enabled = int(frappe.db.get_value('System Settings', None, 'enable_two_factor_auth') or 0)
	if enabled:
		bypass_two_factor_auth = int(frappe.db.get_value('System Settings', None, 'bypass_2fa_for_retricted_ip_users') or 0)
		if bypass_two_factor_auth and user:
			user_doc = frappe.get_doc("User", user)
			restrict_ip_list = user_doc.get_restricted_ip_list() #can be None or one or more than one ip address
			if restrict_ip_list:
				for ip in restrict_ip_list:
					if frappe.local.request_ip.startswith(ip):
						enabled = False
						break

	if not user or not enabled:
		return enabled
	return two_factor_is_enabled_for_(user)

def should_run_2fa(user):
	'''Check if 2fa should run.'''
	return two_factor_is_enabled(user=user)

def get_cached_user_pass():
	'''Get user and password if set.'''
	user = pwd = None
	tmp_id = frappe.form_dict.get('tmp_id')
	if tmp_id:
		user = frappe.safe_decode(frappe.cache().get(tmp_id+'_usr'))
		pwd = frappe.safe_decode(frappe.cache().get(tmp_id+'_pwd'))
	return (user, pwd)

def authenticate_for_2factor(user):
	'''Authenticate two factor for enabled user before login.'''
	if frappe.form_dict.get('otp'):
		return
	otp_secret = get_otpsecret_for_(user)
	token = int(pyotp.TOTP(otp_secret).now())
	tmp_id = frappe.generate_hash(length=8)
	cache_2fa_data(user, token, otp_secret, tmp_id)
	verification_obj = get_verification_obj(user, token, otp_secret)
	# Save data in local
	frappe.local.response['verification'] = verification_obj
	frappe.local.response['tmp_id'] = tmp_id

def cache_2fa_data(user, token, otp_secret, tmp_id):
	'''Cache and set expiry for data.'''
	pwd = frappe.form_dict.get('pwd')
	verification_method = get_verification_method()

	# set increased expiry time for SMS and Email
	if verification_method in ['SMS', 'Email']:
		expiry_time = 300
		frappe.cache().set(tmp_id + '_token', token)
		frappe.cache().expire(tmp_id + '_token', expiry_time)
	else:
		expiry_time = 180
	for k, v in iteritems({'_usr': user, '_pwd': pwd, '_otp_secret': otp_secret}):
		frappe.cache().set("{0}{1}".format(tmp_id, k), v)
		frappe.cache().expire("{0}{1}".format(tmp_id, k), expiry_time)

def two_factor_is_enabled_for_(user):
	'''Check if 2factor is enabled for user.'''
	if user == "Administrator":
		return False

	if isinstance(user, string_types):
		user = frappe.get_doc('User', user)

	roles = [frappe.db.escape(d.role) for d in user.roles or []]
	roles.append("'All'")

	query = """SELECT `name`
		FROM `tabRole`
		WHERE `two_factor_auth`= 1
		AND `name` IN ({0})
		LIMIT 1""".format(", ".join(roles))

	if len(frappe.db.sql(query)) > 0:
		return True

	return False

def get_otpsecret_for_(user):
	'''Set OTP Secret for user even if not set.'''
	otp_secret = frappe.db.get_default(user + '_otpsecret')
	if not otp_secret:
		otp_secret = b32encode(os.urandom(10)).decode('utf-8')
		frappe.db.set_default(user + '_otpsecret', otp_secret)
		frappe.db.commit()
	return otp_secret

def get_verification_method():
	return frappe.db.get_value('System Settings', None, 'two_factor_method')

def confirm_otp_token(login_manager, otp=None, tmp_id=None):
	'''Confirm otp matches.'''
	if not otp:
		otp = frappe.form_dict.get('otp')
	if not otp:
		if two_factor_is_enabled_for_(login_manager.user):
			return False
		return True
	if not tmp_id:
		tmp_id = frappe.form_dict.get('tmp_id')
	hotp_token = frappe.cache().get(tmp_id + '_token')
	otp_secret = frappe.cache().get(tmp_id + '_otp_secret')
	if not otp_secret:
		raise ExpiredLoginException(_('Login session expired, refresh page to retry'))
	hotp = pyotp.HOTP(otp_secret)
	if hotp_token:
		if hotp.verify(otp, int(hotp_token)):
			frappe.cache().delete(tmp_id + '_token')
			return True
		else:
			login_manager.fail(_('Incorrect Verification code'), login_manager.user)

	totp = pyotp.TOTP(otp_secret)
	if totp.verify(otp):
		# show qr code only once
		if not frappe.db.get_default(login_manager.user + '_otplogin'):
			frappe.db.set_default(login_manager.user + '_otplogin', 1)
			delete_qrimage(login_manager.user)
		return True
	else:
		login_manager.fail(_('Incorrect Verification code'), login_manager.user)


def get_verification_obj(user, token, otp_secret):
	otp_issuer = frappe.db.get_value('System Settings', 'System Settings', 'otp_issuer_name')
	verification_method = get_verification_method()
	verification_obj = None
	if verification_method == 'SMS':
		verification_obj = process_2fa_for_sms(user, token, otp_secret)
	elif verification_method == 'OTP App':
		#check if this if the first time that the user is trying to login. If so, send an email
		if not frappe.db.get_default(user + '_otplogin'):
			verification_obj = process_2fa_for_email(user, token, otp_secret, otp_issuer, method='OTP App')
		else:
			verification_obj = process_2fa_for_otp_app(user, otp_secret, otp_issuer)
	elif verification_method == 'Email':
		verification_obj = process_2fa_for_email(user, token, otp_secret, otp_issuer)
	return verification_obj

def process_2fa_for_sms(user, token, otp_secret):
	'''Process sms method for 2fa.'''
	phone = frappe.db.get_value('User', user, ['phone', 'mobile_no'], as_dict=1)
	phone = phone.mobile_no or phone.phone
	status = send_token_via_sms(otp_secret, token=token, phone_no=phone)
	verification_obj = {
		'token_delivery': status,
		'prompt': status and 'Enter verification code sent to {}'.format(phone[:4] + '******' + phone[-3:]),
		'method': 'SMS',
		'setup': status
	}
	return verification_obj

def process_2fa_for_otp_app(user, otp_secret, otp_issuer):
	'''Process OTP App method for 2fa.'''
	totp_uri = pyotp.TOTP(otp_secret).provisioning_uri(user, issuer_name=otp_issuer)
	if frappe.db.get_default(user + '_otplogin'):
		otp_setup_completed = True
	else:
		otp_setup_completed = False

	verification_obj = {
		'totp_uri': totp_uri,
		'method': 'OTP App',
		'qrcode': get_qr_svg_code(totp_uri),
		'setup': otp_setup_completed
	}
	return verification_obj

def process_2fa_for_email(user, token, otp_secret, otp_issuer, method='Email'):
	'''Process Email method for 2fa.'''
	subject = None
	message = None
	status = True
	prompt = ''
	if method == 'OTP App' and not frappe.db.get_default(user + '_otplogin'):
		'''Sending one-time email for OTP App'''
		totp_uri = pyotp.TOTP(otp_secret).provisioning_uri(user, issuer_name=otp_issuer)
		qrcode_link = get_link_for_qrcode(user, totp_uri)
		message = get_email_body_for_qr_code({'qrcode_link': qrcode_link})
		subject = get_email_subject_for_qr_code({'qrcode_link': qrcode_link})
		prompt = _('Please check your registered email address for instructions on how to proceed. Do not close this window as you will have to return to it.')
	else:
		'''Sending email verification'''
		prompt = _('Verification code has been sent to your registered email address.')
	status = send_token_via_email(user, token, otp_secret, otp_issuer, subject=subject, message=message)
	verification_obj = {
		'token_delivery': status,
		'prompt': status and prompt,
		'method': 'Email',
		'setup': status
	}
	return verification_obj

def get_email_subject_for_2fa(kwargs_dict):
	'''Get email subject for 2fa.'''
	subject_template = _('Login Verification Code from {}').format(frappe.db.get_value('System Settings', 'System Settings', 'otp_issuer_name'))
	subject = render_string_template(subject_template, kwargs_dict)
	return subject

def get_email_body_for_2fa(kwargs_dict):
	'''Get email body for 2fa.'''
	body_template = 'Enter this code to complete your login:<br><br> <b>{{otp}}</b>'
	body = render_string_template(body_template, kwargs_dict)
	return body

def get_email_subject_for_qr_code(kwargs_dict):
	'''Get QRCode email subject.'''
	subject_template = _('One Time Password (OTP) Registration Code from {}').format(frappe.db.get_value('System Settings', 'System Settings', 'otp_issuer_name'))
	subject = render_string_template(subject_template, kwargs_dict)
	return subject

def get_email_body_for_qr_code(kwargs_dict):
	'''Get QRCode email body.'''
	body_template = 'Please click on the following link and follow the instructions on the page.<br><br> {{qrcode_link}}'
	body = render_string_template(body_template, kwargs_dict)
	return body

def render_string_template(_str, kwargs_dict):
	'''Render string with jinja.'''
	s = Template(_str)
	s = s.render(**kwargs_dict)
	return s

def get_link_for_qrcode(user, totp_uri):
	'''Get link to temporary page showing QRCode.'''
	key = frappe.generate_hash(length=20)
	key_user = "{}_user".format(key)
	key_uri = "{}_uri".format(key)
	lifespan = int(frappe.db.get_value('System Settings', 'System Settings', 'lifespan_qrcode_image'))
	if lifespan<=0:
		lifespan = 240
	frappe.cache().set_value(key_uri, totp_uri, expires_in_sec=lifespan)
	frappe.cache().set_value(key_user, user, expires_in_sec=lifespan)
	return get_url('/qrcode?k={}'.format(key))

def send_token_via_sms(otpsecret, token=None, phone_no=None):
	'''Send token as sms to user.'''
	try:
		from frappe.core.doctype.sms_settings.sms_settings import send_request
	except:
		return False

	if not phone_no:
		return False

	ss = frappe.get_doc('SMS Settings', 'SMS Settings')
	if not ss.sms_gateway_url:
		return False

	hotp = pyotp.HOTP(otpsecret)
	args = {
		ss.message_parameter: 'Your verification code is {}'.format(hotp.at(int(token)))
	}

	for d in ss.get("parameters"):
		args[d.parameter] = d.value

	args[ss.receiver_parameter] = phone_no

	sms_args = {
		'params': args,
		'gateway_url': ss.sms_gateway_url,
		'use_post': ss.use_post
	}
	enqueue(method=send_request, queue='short', timeout=300, event=None,
		is_async=True, job_name=None, now=False, **sms_args)
	return True

def send_token_via_email(user, token, otp_secret, otp_issuer, subject=None, message=None):
	'''Send token to user as email.'''
	user_email = frappe.db.get_value('User', user, 'email')
	if not user_email:
		return False
	hotp = pyotp.HOTP(otp_secret)
	otp = hotp.at(int(token))
	template_args = {'otp': otp, 'otp_issuer': otp_issuer}
	if not subject:
		subject = get_email_subject_for_2fa(template_args)
	if not message:
		message = get_email_body_for_2fa(template_args)

	email_args = {
		'recipients': user_email,
		'sender': None,
		'subject': subject,
		'message': message,
		'header': [_('Verfication Code'), 'blue'],
		'delayed': False,
		'retry':3
	}

	enqueue(method=frappe.sendmail, queue='short', timeout=300, event=None,
		is_async=True, job_name=None, now=False, **email_args)
	return True

def get_qr_svg_code(totp_uri):
	'''Get SVG code to display Qrcode for OTP.'''
	url = qrcreate(totp_uri)
	svg = ''
	stream = BytesIO()
	try:
		url.svg(stream, scale=4, background="#eee", module_color="#222")
		svg = stream.getvalue().decode().replace('\n', '')
		svg = b64encode(svg.encode())
	finally:
		stream.close()
	return svg

def qrcode_as_png(user, totp_uri):
	'''Save temporary Qrcode to server.'''
	folder = create_barcode_folder()
	png_file_name = '{}.png'.format(frappe.generate_hash(length=20))
	_file = frappe.get_doc({
		"doctype": "File",
		"file_name": png_file_name,
		"attached_to_doctype": 'User',
		"attached_to_name": user,
		"folder": folder,
		"content": png_file_name})
	_file.save()
	frappe.db.commit()
	file_url = get_url(_file.file_url)
	file_path = os.path.join(frappe.get_site_path('public', 'files'), _file.file_name)
	url = qrcreate(totp_uri)
	with open(file_path, 'w') as png_file:
		url.png(png_file, scale=8, module_color=[0, 0, 0, 180], background=[0xff, 0xff, 0xcc])
	return file_url

def create_barcode_folder():
	'''Get Barcodes folder.'''
	folder_name = 'Barcodes'
	folder = frappe.db.exists('File', {'file_name': folder_name})
	if folder:
		return folder
	folder = frappe.get_doc({
			'doctype': 'File',
			'file_name': folder_name,
			'is_folder':1,
			'folder': 'Home'
		})
	folder.insert(ignore_permissions=True)
	return folder.name

def delete_qrimage(user, check_expiry=False):
	'''Delete Qrimage when user logs in.'''
	user_barcodes = frappe.get_all('File', {'attached_to_doctype': 'User',
		'attached_to_name': user, 'folder': 'Home/Barcodes'})

	for barcode in user_barcodes:
		if check_expiry and not should_remove_barcode_image(barcode):
			continue
		barcode = frappe.get_doc('File', barcode.name)
		frappe.delete_doc('File', barcode.name, ignore_permissions=True)

def delete_all_barcodes_for_users():
	'''Task to delete all barcodes for user.'''
	if not two_factor_is_enabled():
		return

	users = frappe.get_all('User', {'enabled':1})
	for user in users:
		delete_qrimage(user.name, check_expiry=True)

def should_remove_barcode_image(barcode):
	'''Check if it's time to delete barcode image from server. '''
	if isinstance(barcode, string_types):
		barcode = frappe.get_doc('File', barcode)
	lifespan = frappe.db.get_value('System Settings', 'System Settings', 'lifespan_qrcode_image')
	if time_diff_in_seconds(get_datetime(), barcode.creation) > int(lifespan):
		return True
	return False

def disable():
	frappe.db.set_value('System Settings', None, 'enable_two_factor_auth', 0)
