# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

import webnotes

def get_hooks():
	return {
		"app_include_js": ["assets/js/webnotes.min.js"],
		"app_include_css": ["assets/webnotes/css/splash.css", "assets/css/webnotes.css"],
		"desktop_icons": get_desktop_icons()
	}

def after_install():
	# reset installed apps for re-install
	webnotes.conn.set_global("installed_apps", "[]")
	
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
		webnotes.bean(d).insert()

	# all roles to admin
	webnotes.bean("Profile", "Administrator").get_controller().add_roles(*webnotes.conn.sql_list("""
		select name from tabRole"""))

	# update admin password
	from webnotes.auth import _update_password
	_update_password("Administrator", webnotes.conf.get("admin_password"))

	webnotes.conn.commit()

		
def get_desktop_icons():
	return {
		"Calendar": {
			"color": "#2980b9", 
			"icon": "icon-calendar", 
			"label": "Calendar", 
			"link": "Calendar/Event", 
			"type": "view"
		}, 
		"Finder": {
			"color": "#14C7DE", 
			"icon": "icon-folder-open", 
			"label": "Finder", 
			"link": "finder", 
			"type": "page"
		}, 
		"Messages": {
			"color": "#9b59b6", 
			"icon": "icon-comments", 
			"label": "Messages", 
			"link": "messages", 
			"type": "page"
		}, 
		"To Do": {
			"color": "#f1c40f", 
			"icon": "icon-check", 
			"label": "To Do", 
			"link": "todo", 
			"type": "page"
		}, 
		"Website": {
			"color": "#16a085", 
			"icon": "icon-globe", 
			"link": "website-home", 
			"type": "module"
		}
	}