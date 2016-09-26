# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe

from frappe.model.db_schema import DbManager
from frappe.installer import get_root_connection
from frappe.database import Database
import os

help_db_name = '_frappe_help'

def sync():
	# make table
	help_db = HelpDatabase()
	help_db.make_table()
	help_db.sync_pages()

@frappe.whitelist()
def get_help(text):
	return HelpDatabase().search(text)

class HelpDatabase(object):
	def __init__(self):
		self.make_database()
		self.connect()

	def make_database(self):
		dbman = DbManager(get_root_connection())

		# make database
		if not help_db_name in dbman.get_database_list():
			dbman.create_user(help_db_name, help_db_name)
			dbman.create_database(help_db_name)
			dbman.grant_all_privileges(help_db_name, help_db_name)
			dbman.flush_privileges()

	def connect(self):
		self.db = Database(user=help_db_name, password=help_db_name)

	def make_table(self):
		if not 'help' in self.db.get_tables():
			self.db.sql('''create table help(path text, content text, fulltext(content))
				COLLATE=utf8mb4_unicode_ci
				ENGINE=MyISAM
				CHARACTER SET=utf8mb4''')

	def search(self, words):
		return self.db.sql('select path, content from help where match(content) against (%s) limit 10', words)

	def sync_pages(self):
		self.db.sql('truncate help')
		for app in os.listdir('../apps'):
			docs_folder = '../apps/{app}/{app}/docs/user'.format(app=app)
			if os.path.exists(docs_folder):
				for basepath, folders, files in os.walk(docs_folder):
					for fname in files:
						if fname.rsplit('.', 1)[-1] in ('md', 'html'):
							fpath = os.path.join(basepath, fname)
							with open(fpath, 'r') as f:
								#relpath = os.path.relpath(fpath, '../apps/{app}'.format(app=app))
								self.db.sql('''insert into help(path, content)
									values (%s, %s)''', (fpath, f.read()))

