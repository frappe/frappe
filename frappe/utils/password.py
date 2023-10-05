# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from cryptography.fernet import Fernet, InvalidToken
from passlib.context import CryptContext
from pypika.terms import Values

import frappe
from frappe import _
from frappe.query_builder import Table
from frappe.utils import cstr, encode

Auth = Table("__Auth")


passlibctx = CryptContext(
	schemes=[
		"pbkdf2_sha256",
		"argon2",
	],
)


def get_decrypted_password(doctype, name, fieldname="password", raise_exception=True):
    """
    Retrieve and decrypt a password from the Auth table.

    This function queries the Auth table to find the encrypted password associated
    with the specified document, name, and fieldname. If a password is found,
    it is decrypted and returned. If no password is found and raise_exception
    is True, an AuthenticationError is raised with an error message.

    Args:
        doctype (str): The document type.
        name (str): The name of the document.
        fieldname (str, optional): The name of the field storing the password.
        Defaults to "password".
        raise_exception (bool, optional): Whether to raise an exception if the
            password is not found. Defaults to True.

    Returns:
        str: The decrypted password.

    Raises:
        frappe.AuthenticationError: If the password is not found and raise_exception is True.
    """
    result = (
    	frappe.qb.from_(Auth)
    	.select(Auth.password)
    	.where(
    		(Auth.doctype == doctype)
    		& (Auth.name == name)
    		& (Auth.fieldname == fieldname)
    		& (Auth.encrypted == 1)
    	)
    	.limit(1)
    ).run()

    if result and result[0][0]:
        return decrypt(result[0][0])

    elif raise_exception:
        frappe.throw(
        	_("Password not found for {0} {1} {2}").format(doctype, name, fieldname),
        	frappe.AuthenticationError,
        )


def set_encrypted_password(doctype, name, pwd, fieldname="password"):
    """
    Set the encrypted password for a specified doctype, name, and fieldname.

    This function takes four arguments:
        - doctype (str): The type of document.
        - name (str): The name of the document.
        - pwd: The password to be encrypted.
        - fieldname (str): The name of the field where the password will be stored.
        Defaults to 'password'.

    The function creates a query using the frappe.qb module to insert the doctype,
    name, fieldname, encrypted password, and a flag indicating encryption into the
    Auth table. The query is then executed using the run() method.

    If the database type is mariadb, the query is modified to update the password
    on duplicate key. If the database type is postgres, the query is modified
    to update the password on conflict.

    If a frappe.db.DataError exception is raised, the function checks if the error
    is caused by a password that is too long and throws an exception if necessary.
    """
    query = (
    	frappe.qb.into(Auth)
    	.columns(Auth.doctype, Auth.name, Auth.fieldname, Auth.password, Auth.encrypted)
    	.insert(doctype, name, fieldname, encrypt(pwd), 1)
    )

    # TODO: Simplify this via aliasing methods in `frappe.qb`
    if frappe.db.db_type == "mariadb":
        query = query.on_duplicate_key_update(Auth.password, Values(Auth.password))
    elif frappe.db.db_type == "postgres":
        query = query.on_conflict(Auth.doctype, Auth.name, Auth.fieldname).do_update(Auth.password)

    try:
        query.run()

    except frappe.db.DataError as e:
        if frappe.db.is_data_too_long(e):
            frappe.throw(_("Most probably your password is too long."), exc=e)
        raise e


def remove_encrypted_password(doctype, name, fieldname="password"):
    """
    Remove the encrypted password for a specified doctype, name, and fieldname.

    This function takes three arguments:
        - doctype (str): The type of document.
        - name (str): The name of the document.
        - fieldname (str): The name of the field where the password is stored. Defaults
        to 'password'.

    The function deletes the record from the __Auth table that matches the provided
    doctype, name, and fieldname.
    """
    frappe.db.delete("__Auth", {"doctype": doctype, "name": name, "fieldname": fieldname})


def check_password(user, pwd, doctype="User", fieldname="password", delete_tracker_cache=True):
    """Checks if user and password are correct, else raises frappe.AuthenticationError"""

    result = (
    	frappe.qb.from_(Auth)
    	.select(Auth.name, Auth.password)
    	.where(
    		(Auth.doctype == doctype)
    		& (Auth.name == user)
    		& (Auth.fieldname == fieldname)
    		& (Auth.encrypted == 0)
    	)
    	.limit(1)
    	.run(as_dict=True)
    )

    if not result or not passlibctx.verify(pwd, result[0].password):
        raise frappe.AuthenticationError(_("Incorrect User or Password"))

    # lettercase agnostic
    user = result[0].name

    # TODO: This need to be deleted after checking side effects of it.
    # We have a `LoginAttemptTracker` that can take care of tracking related cache.
    if delete_tracker_cache:
        delete_login_failed_cache(user)

    if passlibctx.needs_update(result[0].password):
        update_password(user, pwd, doctype, fieldname)

    return user


def delete_login_failed_cache(user):
    """Deletes the login failed cache for a given user."""
    frappe.cache.hdel("last_login_tried", user)
    frappe.cache.hdel("login_failed_count", user)
    frappe.cache.hdel("locked_account_time", user)


def update_password(user, pwd, doctype="User", fieldname="password", logout_all_sessions=False):
    """
	Update the password for the User

	:param user: username
	:param pwd: new password
	:param doctype: doctype name (for encryption)
	:param fieldname: fieldname (in given doctype) (for encryption)
	:param logout_all_session: delete all other session
	"""
    hashPwd = passlibctx.hash(pwd)

    query = (
    	frappe.qb.into(Auth)
    	.columns(Auth.doctype, Auth.name, Auth.fieldname, Auth.password, Auth.encrypted)
    	.insert(doctype, user, fieldname, hashPwd, 0)
    )

    # TODO: Simplify this via aliasing methods in `frappe.qb`
    if frappe.db.db_type == "mariadb":
        query = query.on_duplicate_key_update(Auth.password, hashPwd).on_duplicate_key_update(
        	Auth.encrypted, 0
        )
    elif frappe.db.db_type == "postgres":
        query = (
        	query.on_conflict(Auth.doctype, Auth.name, Auth.fieldname)
        	.do_update(Auth.password, hashPwd)
        	.do_update(Auth.encrypted, 0)
        )

    query.run()

    # clear all the sessions except current
    if logout_all_sessions:
        from frappe.sessions import clear_sessions

        clear_sessions(user=user, keep_current=True, force=True)


def delete_all_passwords_for(doctype, name):
    try:
        frappe.db.delete("__Auth", {"doctype": doctype, "name": name})
    except Exception as e:
        if not frappe.db.is_missing_column(e):
            raise


def rename_password(doctype, old_name, new_name):
    """
    Renames a password in the Auth table.

    Args:
        doctype (str): The document type of the password.
        old_name (str): The old name of the password.
        new_name (str): The new name of the password.
    """
    # NOTE: fieldname is not considered, since the document is renamed
    frappe.qb.update(Auth).set(Auth.name, new_name).where(
    	(Auth.doctype == doctype) & (Auth.name == old_name)
    ).run()


def rename_password_field(doctype, old_fieldname, new_fieldname):
    """
    Renames a password field in the Auth table.

    Args:
        doctype (str): The document type of the password field.
        old_fieldname (str): The old fieldname of the password.
        new_fieldname (str): The new fieldname of the password.
    """
    frappe.qb.update(Auth).set(Auth.fieldname, new_fieldname).where(
    	(Auth.doctype == doctype) & (Auth.fieldname == old_fieldname)
    ).run()


def create_auth_table():
    """
    Creates the Auth table.
    """
    # same as Framework.sql
    frappe.db.create_auth_table()


def encrypt(txt, encryption_key=None):
    """
    Encrypts a given text using the provided encryption key.

    Args:
        txt (str): The text to be encrypted.
        encryption_key (str, optional): The encryption key. Defaults to None.

    Returns:
        str: The encrypted text.
    """
    # Only use Fernet.generate_key().decode() to enter encyption_key value

    try:
        cipher_suite = Fernet(encode(encryption_key or get_encryption_key()))
    except Exception:
        # encryption_key is not in 32 url-safe base64-encoded format
        frappe.throw(_("Encryption key is in invalid format!"))

    return cstr(cipher_suite.encrypt(encode(txt)))


def decrypt(txt, encryption_key=None):
    # Only use encryption_key value generated with Fernet.generate_key().decode()

    try:
        cipher_suite = Fernet(encode(encryption_key or get_encryption_key()))
        return cstr(cipher_suite.decrypt(encode(txt)))
    except InvalidToken:
        # encryption_key in site_config is changed and not valid
        frappe.throw(
        	_("Encryption key is invalid! Please check site_config.json")
        	+ "<br>"
        	+ _(
        		"If you have recently restored the site you may need to copy the site config contaning original Encryption Key."
        	)
        )


def get_encryption_key():
    if "encryption_key" not in frappe.local.conf:
        from frappe.installer import update_site_config

        encryption_key = Fernet.generate_key().decode()
        update_site_config("encryption_key", encryption_key)
        frappe.local.conf.encryption_key = encryption_key

    return frappe.local.conf.encryption_key


def get_password_reset_limit():
    return frappe.db.get_single_value("System Settings", "password_reset_limit") or 0
