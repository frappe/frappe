# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cstr, encode
from cryptography.fernet import Fernet, InvalidToken 

def get_decrypted_password(doctype, name, fieldname='password', raise_exception=True):
	auth = frappe.db.sql('''select `password` from `__Auth`
		where doctype=%(doctype)s and name=%(name)s and fieldname=%(fieldname)s and encrypted=1''',
		{ 'doctype': doctype, 'name': name, 'fieldname': fieldname })

	if auth and auth[0][0]:
		return decrypt(auth[0][0])

	elif raise_exception:
		frappe.throw(_('Password not found'), frappe.AuthenticationError)

def set_encrypted_password(doctype, name, pwd, fieldname='password'):
	frappe.db.sql("""insert into __Auth (doctype, name, fieldname, `password`, encrypted)
		values (%(doctype)s, %(name)s, %(fieldname)s, %(pwd)s, 1)
		on duplicate key update `password`=%(pwd)s, encrypted=1""",
		{ 'doctype': doctype, 'name': name, 'fieldname': fieldname, 'pwd': encrypt(pwd) })

def check_password(user, pwd, doctype='User', fieldname='password'):
	'''Checks if user and password are correct, else raises frappe.AuthenticationError'''

	auth = frappe.db.sql("""select name, `password`, salt from `__Auth`
		where doctype=%(doctype)s and name=%(name)s and fieldname=%(fieldname)s and encrypted=0
		and (
			(salt is null and `password`=password(%(pwd)s))
			or `password`=password(concat(%(pwd)s, salt))
		)""",{ 'doctype': doctype, 'name': user, 'fieldname': fieldname, 'pwd': pwd }, as_dict=True)

	if not auth:
		raise frappe.AuthenticationError('Incorrect User or Password')

	salt = auth[0].salt
	if not salt:
		# sets salt and updates password
		update_password(user, pwd, doctype, fieldname)

	# lettercase agnostic
	user = auth[0].name

	return user

def update_password(user, pwd, doctype='User', fieldname='password'):
	salt = frappe.generate_hash()

	frappe.db.sql("""insert into __Auth (doctype, name, fieldname, `password`, salt, encrypted)
		values (%(doctype)s, %(name)s, %(fieldname)s, password(concat(%(pwd)s, %(salt)s)), %(salt)s, 0)
		on duplicate key update
			`password`=password(concat(%(pwd)s, %(salt)s)), salt=%(salt)s, encrypted=0""",
		{ 'doctype': doctype, 'name': user, 'fieldname': fieldname, 'pwd': pwd, 'salt': salt })

def delete_all_passwords_for(doctype, name):
	try:
		frappe.db.sql("""delete from __Auth where doctype=%(doctype)s and name=%(name)s""",
			{ 'doctype': doctype, 'name': name })
	except Exception as e:
		if e.args[0]!=1054:
			raise

def rename_password(doctype, old_name, new_name):
	# NOTE: fieldname is not considered, since the document is renamed
	frappe.db.sql("""update __Auth set name=%(new_name)s
		where doctype=%(doctype)s and name=%(old_name)s""",
		{ 'doctype': doctype, 'new_name': new_name, 'old_name': old_name })

def rename_password_field(doctype, old_fieldname, new_fieldname):
	frappe.db.sql('''update `__Auth` set fieldname=%(new_fieldname)s
		where doctype=%(doctype)s and fieldname=%(old_fieldname)s''',
		{ 'doctype': doctype, 'old_fieldname': old_fieldname, 'new_fieldname': new_fieldname })

def create_auth_table():
	# same as Framework.sql
	frappe.db.sql_ddl("""create table if not exists __Auth (
			`doctype` VARCHAR(140) NOT NULL,
			`name` VARCHAR(255) NOT NULL,
			`fieldname` VARCHAR(140) NOT NULL,
			`password` VARCHAR(255) NOT NULL,
			`salt` VARCHAR(140),
			`encrypted` INT(1) NOT NULL DEFAULT 0,
			PRIMARY KEY (`doctype`, `name`, `fieldname`)
		) ENGINE=InnoDB ROW_FORMAT=COMPRESSED CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")

def encrypt(pwd):
	if len(pwd) > 100:
		# encrypting > 100 chars will lead to truncation
		frappe.throw(_('Password cannot be more than 100 characters long'))

	cipher_suite = Fernet(encode(get_encryption_key()))
	cipher_text = cstr(cipher_suite.encrypt(encode(pwd)))
	return cipher_text

def decrypt(pwd):
	try:
		cipher_suite = Fernet(encode(get_encryption_key()))
		plain_text = cstr(cipher_suite.decrypt(encode(pwd)))
		return plain_text
	except InvalidToken:
		# encryption_key in site_config is changed and not valid
		frappe.throw(_('Encryption key is invalid, Please check site_config.json'))

def get_encryption_key():
	from frappe.installer import update_site_config

	if 'encryption_key' not in frappe.local.conf:
		encryption_key = Fernet.generate_key().decode()
		update_site_config('encryption_key', encryption_key)
		frappe.local.conf.encryption_key = encryption_key

	return frappe.local.conf.encryption_key
