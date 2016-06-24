# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
import frappe.translate
import frappe.modules.patch_handler
import frappe.model.sync
from frappe.utils.fixtures import sync_fixtures
from frappe.sessions import clear_global_cache
from frappe.desk.notifications import clear_notifications
from frappe.website import render
from frappe.desk.doctype.desktop_icon.desktop_icon import sync_desktop_icons

def migrate(verbose=True, rebuild_website=False):
	'''Migrate all apps to the latest version, will:

	- run patches
	- sync doctypes (schema)
	- sync fixtures
	- sync desktop icons
	- sync web pages (from /www)'''
	clear_global_cache()

	# run patches
	frappe.modules.patch_handler.run_all()
	# sync
	frappe.model.sync.sync_all(verbose=verbose)
	frappe.translate.clear_cache()
	sync_fixtures()
	sync_desktop_icons()
	frappe.get_doc('Portal Settings', 'Portal Settings').sync_menu()

	# syncs statics
	render.clear_cache()

	frappe.db.commit()

	clear_notifications()

	frappe.publish_realtime("version-update")
