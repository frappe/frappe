# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest
import os, subprocess, shutil
import frappe, json

class TestBenchCommands(unittest.TestCase):
	def setUp(self):
		# Create a new bench using 'bench init'
		bench_init_cmd = ['bench', 'init', 'test-bench']
		self.home_dir = os.path.expanduser('~')

		success = subprocess.check_output(bench_init_cmd, cwd=self.home_dir)

		# Get the bench path
		self.bench_path = os.path.join(self.home_dir, 'test-bench')

	def tearDown(self):
		# Delete the bench created
		if os.path.exists(self.bench_path):
			shutil.rmtree(self.bench_path)

	def test_drop_site(self):
		# Create a new site on the bench
		new_site_cmd = ['bench', 'new-site', 'test-drop.site', '--admin-password', 'admin']

		if os.environ.get('TRAVIS'):
			new_site_cmd.extend(['--mariadb-root-password', 'travis'])

		success = subprocess.check_output(new_site_cmd, cwd=self.bench_path)

		# Drop site
		drop_site_cmd = ['bench', 'drop-site', 'test-drop.site', '--root-password', 'travis']

		success = subprocess.check_output(drop_site_cmd, cwd=self.bench_path)

		# Asserts
		# Site folder not present in the sites directory
		base_site_path = os.path.join(self.bench_path, 'sites')
		site_path = os.path.join(base_site_path, 'test-drop.site')
		self.assertFalse(os.path.exists(site_path))

		# Archived sites path and archived sites list in common_site_config.json
		common_site_config_path = os.path.join(base_site_path, 'common_site_config.json')

		print os.listdir(os.path.join(self.bench_path, 'sites')), os.listdir(self.bench_path)

		with open(common_site_config_path, mode='r') as f:
			config = json.load(f)

		# self.assertTrue(hasattr(config, 'archived_sites_path'))
		# self.assertEqual(config.get('archived_sites_path'), os.path.join(self.home_dir, 'archived_sites'))
		#
		# self.assertTrue(hasattr(config, 'archived_sites'))
		# archived_sites = config.get('archived_sites')
		# self.assertItemsEqual(archived_sites, 'test-drop.site')
