# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe

from frappe.model.db_schema import DbManager
from frappe.installer import get_root_connection
from frappe.database import Database
import os
import re
from markdown2 import markdown

help_db_name = '_frappe_help'

def sync():
	# make table
	help_db = HelpDatabase()
	help_db.make_table()
	help_db.sync_pages()

@frappe.whitelist()
def get_help(text):
	return HelpDatabase().search(text)

@frappe.whitelist()
def get_help_content(path):
	return HelpDatabase().get_content(path)

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
			self.db.sql('''create table help(path text, content text, title text, intro text, fulltext(content))
				COLLATE=utf8mb4_unicode_ci
				ENGINE=MyISAM
				CHARACTER SET=utf8mb4''')

	def search(self, words):
		return self.db.sql('select title, intro, path from help where match(content) against (%s) limit 10', words)

	def get_content(self, path):
		return self.db.sql('select content from help where path like "%{path}%"'.format(path=path))

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
								title = self.get_title(basepath, fname)
								content = frappe.render_template(unicode(f.read(), 'utf-8'),
									{'docs_base_url': '/assets/{app}_docs'.format(app=app)})
								content = self.build_content(content, fpath)
								intro = self.get_intro(content)
								#relpath = os.path.relpath(fpath, '../apps/{app}'.format(app=app))
								self.db.sql('''insert into help(path, content, title, intro)
									values (%s, %s, %s, %s)''', (fpath, content, title, intro))

	def get_title(self, basepath, filename):
		if 'index' in filename:
			title = basepath.rsplit('/', 1)[-1].title()
		else:
			title = filename.rsplit('.', 1)[0]
			title = title.title().replace("-", " ")
		return title

	def get_intro(self, content):
		html = markdown(content)
		intro = ""
		if '<p>' in html:
			intro = html.split('<p>', 1)[1].split('</p>', 1)[0]
		if 'Duration' in html:
			intro = "Help Video: " + intro
		return intro

	def build_content(self, content, path):
		if '{index}' in content:
			path = path.rsplit("/", 1)[0]
			index_path = os.path.join(path, "index.txt")
			if os.path.exists(index_path):
				with open(index_path, 'r') as f:
					lines = f.read().split('\n')
					html = "<ol class='index-links'>"
					for line in lines:
						fpath = os.path.join(path, line)
						title = line.title().replace("-", " ")
						if title:
							html += "<li><a data-path='{fpath}'> {title} </a></li>".format(fpath=fpath, title=title)
					content = content.replace('{index}', html)

		if '{next}' in content:
			content = content.replace('{next}', '')

		return content
