# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import unittest

import frappe

from .google_settings import get_file_picker_settings


class TestGoogleSettings(unittest.TestCase):
	def setUp(self):
		settings = frappe.get_single("Google Settings")
		settings.client_id = "test_client_id"
		settings.app_id = "test_app_id"
		settings.api_key = "test_api_key"
		settings.save()

	def test_picker_disabled(self):
		"""Google Drive Picker should be disabled if it is not enabled in Google Settings."""
		frappe.db.set_value("Google Settings", None, "enable", 1)
		frappe.db.set_value("Google Settings", None, "google_drive_picker_enabled", 0)
		settings = get_file_picker_settings()

		self.assertEqual(settings, {})

	def test_google_disabled(self):
		"""Google Drive Picker should be disabled if Google integration is not enabled."""
		frappe.db.set_value("Google Settings", None, "enable", 0)
		frappe.db.set_value("Google Settings", None, "google_drive_picker_enabled", 1)
		settings = get_file_picker_settings()

		self.assertEqual(settings, {})

	def test_picker_enabled(self):
		"""If picker is enabled, get_file_picker_settings should return the credentials."""
		frappe.db.set_value("Google Settings", None, "enable", 1)
		frappe.db.set_value("Google Settings", None, "google_drive_picker_enabled", 1)
		settings = get_file_picker_settings()

		self.assertEqual(True, settings.get("enabled", False))
		self.assertEqual("test_client_id", settings.get("clientId", ""))
		self.assertEqual("test_app_id", settings.get("appId", ""))
		self.assertEqual("test_api_key", settings.get("developerKey", ""))
