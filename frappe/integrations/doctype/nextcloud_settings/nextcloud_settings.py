# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils.background_jobs import enqueue
from frappe.integrations.doctype.nextcloud_settings.nextcloud_controller import NextCloudController

class NextCloudSettings(Document):

	def validate(self):
		if not self.enabled:
			return

@frappe.whitelist()
def take_backup():
	"""Enqueue longjob for taking backup to nextcloud"""
	enqueue("frappe.integrations.doctype.nextcloud_settings.nextcloud_settings.start_backup", queue='long', timeout=1500)
	frappe.msgprint(_("Queued for backup. It may take a few minutes to an hour."))

def take_backups_daily():
	take_backups_if("Daily")

def take_backups_weekly():
	take_backups_if("Weekly")

def take_backups_if(freq):
	if frappe.db.get_value("NextCloud Settings", None, "backup_frequency") == freq:
		start_backup()

def start_backup():
	backup = NextCloudController()
	backup.take_backup_nextcloud()
