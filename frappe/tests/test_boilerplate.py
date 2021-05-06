import os
import unittest
from unittest.mock import patch

import frappe
from frappe.utils.boilerplate import make_boilerplate


class TestBoilerPlate(unittest.TestCase):
	def test_create_app(self):
		title = "Test App"
		description = "Test app for unit testing"
		publisher = "Test Publisher"
		email = "example@example.org"
		icon = ""  # empty -> default
		color = ""
		app_license = "MIT"

		user_input = [
			title,
			description,
			publisher,
			email,
			icon,
			color,
			app_license,
		]

		bench_path = frappe.utils.get_bench_path()
		apps_dir = os.path.join(bench_path, "apps")
		app_name = "test_app"

		with patch("builtins.input", side_effect=user_input):
			make_boilerplate(apps_dir, app_name)

		root_paths = [
			app_name,
			"requirements.txt",
			"README.md",
			"setup.py",
			"license.txt",
			".git",
		]
		paths_inside_app = [
			"__init__.py",
			"hooks.py",
			"patches.txt",
			"templates",
			"www",
			"config",
			"modules.txt",
			"public",
			app_name,
		]

		new_app_dir = os.path.join(bench_path, apps_dir, app_name)

		all_paths = list()

		for path in root_paths:
			all_paths.append(os.path.join(new_app_dir, path))

		for path in paths_inside_app:
			all_paths.append(os.path.join(new_app_dir, app_name, path))

		for path in all_paths:
			self.assertTrue(os.path.exists(path), msg=f"{path} should exist in new app")
