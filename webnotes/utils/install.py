# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

import webnotes

def before_install():
	webnotes.reload_doc("core", "doctype", "docfield")
	webnotes.reload_doc("core", "doctype", "docperm")
	webnotes.reload_doc("core", "doctype", "doctype")

def after_install():
	# reset installed apps for re-install
	webnotes.conn.set_global("installed_apps", '["webnotes"]')
	
	# core users / roles
	install_docs = [
		{'doctype':'Profile', 'name':'Administrator', 'first_name':'Administrator', 
			'email':'admin@localhost', 'enabled':1},
		{'doctype':'Profile', 'name':'Guest', 'first_name':'Guest',
			'email':'guest@localhost', 'enabled':1},
		{'doctype':'UserRole', 'parent': 'Administrator', 'role': 'Administrator', 
			'parenttype':'Profile', 'parentfield':'user_roles'},
		{'doctype':'UserRole', 'parent': 'Guest', 'role': 'Guest', 
			'parenttype':'Profile', 'parentfield':'user_roles'},
		{'doctype': "Role", "role_name": "Report Manager"}
	]
	
	for d in install_docs:
		try:
			webnotes.bean(d).insert()
		except NameError:
			pass

	# all roles to admin
	webnotes.bean("Profile", "Administrator").get_controller().add_roles(*webnotes.conn.sql_list("""
		select name from tabRole"""))

	# update admin password
	from webnotes.auth import _update_password
	_update_password("Administrator", webnotes.conf.get("admin_password"))

	webnotes.conn.commit()
