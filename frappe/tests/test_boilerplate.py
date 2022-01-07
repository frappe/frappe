import ast
import glob
import os
import shutil
import unittest
from unittest.mock import patch

import frappe
from frappe.utils.boilerplate import make_boilerplate


class TestBoilerPlate(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		title = "Test App"
		description = "This app's description contains 'single quotes' and \"double quotes\"."
		publisher = "Test Publisher"
		email = "example@example.org"
		icon = ""  # empty -> default
		color = ""
		app_license = "MIT"

		cls.user_input = [
			title,
			description,
			publisher,
			email,
			icon,
			color,
			app_license,
		]

		cls.bench_path = frappe.utils.get_bench_path()
		cls.apps_dir = os.path.join(cls.bench_path, "apps")
		cls.app_names = ("test_app", "test_app_no_git")
		cls.gitignore_file = ".gitignore"
		cls.git_folder = ".git"

		cls.root_paths = [
			"requirements.txt",
			"README.md",
			"setup.py",
			"license.txt",
			cls.git_folder,
			cls.gitignore_file
		]
		cls.paths_inside_app = [
			"__init__.py",
			"hooks.py",
			"patches.txt",
			"templates",
			"www",
			"config",
			"modules.txt",
			"public"
		]

	@classmethod
	def tearDownClass(cls):
		test_app_dirs = (os.path.join(cls.bench_path, "apps", app_name) for app_name in cls.app_names)
		for test_app_dir in test_app_dirs:
			if os.path.exists(test_app_dir):
				shutil.rmtree(test_app_dir)

	def test_create_app(self):
		with patch("builtins.input", side_effect=self.user_input):
			make_boilerplate(self.apps_dir, self.app_names[0])

		new_app_dir = os.path.join(self.bench_path, self.apps_dir, self.app_names[0])

		paths = self.get_paths(new_app_dir, self.app_names[0])
		for path in paths:
			self.assertTrue(
				os.path.exists(path),
				msg=f"{path} should exist in {self.app_names[0]} app"
			)

		self.check_parsable_python_files(new_app_dir)

	def test_create_app_without_git_init(self):
		with patch("builtins.input", side_effect=self.user_input):
			make_boilerplate(self.apps_dir, self.app_names[1], no_git=True)

		new_app_dir = os.path.join(self.apps_dir, self.app_names[1])

		paths = self.get_paths(new_app_dir, self.app_names[1])
		for path in paths:
			if os.path.basename(path) in (self.git_folder, self.gitignore_file):
				self.assertFalse(
					os.path.exists(path),
					msg=f"{path} shouldn't exist in {self.app_names[1]} app"
				)
			else:
				self.assertTrue(
					os.path.exists(path),
					msg=f"{path} should exist in {self.app_names[1]} app"
				)

		self.check_parsable_python_files(new_app_dir)

	def get_paths(self, app_dir, app_name):
		all_paths = list()

		for path in self.root_paths:
			all_paths.append(os.path.join(app_dir, path))

		all_paths.append(os.path.join(app_dir, app_name))

		for path in self.paths_inside_app:
			all_paths.append(os.path.join(app_dir, app_name, path))

		return all_paths

	def check_parsable_python_files(self, app_dir):
		# check if python files are parsable
		python_files = glob.glob(app_dir + "**/*.py", recursive=True)

		for python_file in python_files:
			with open(python_file) as p:
				try:
					ast.parse(p.read())
				except Exception as e:
					self.fail(f"Can't parse python file in new app: {python_file}\n" + str(e))
