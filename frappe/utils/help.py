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
from bs4 import BeautifulSoup

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
			self.db.sql('''create table help(path text, content text, title text, intro text, fulltext(title), fulltext(content))
				COLLATE=utf8mb4_unicode_ci
				ENGINE=MyISAM
				CHARACTER SET=utf8mb4''')

	def search(self, words):
		return self.db.sql('select title, intro, path from help where match(content) against (%s) limit 10', words)

	def get_content(self, path):
		query = 'select title, content from help where path like "%{path}%" order by path desc'
		path2 = path
		if not path2.endswith('index'):
			path2 += "index" if path2.endswith('/') else "/index"
		result = self.db.sql(query.format(path=path2))
		if not result:
			result = self.db.sql(query.format(path=path))
		return result

	def sync_pages(self):
		self.db.sql('truncate help')
		for app in os.listdir('../apps'):
			docs_folder = '../apps/{app}/{app}/docs/user'.format(app=app)
			if os.path.exists(docs_folder):
				for basepath, folders, files in os.walk(docs_folder):
					files = self.reorder_files(files)
					for fname in files:
						if fname.rsplit('.', 1)[-1] in ('md', 'html'):
							fpath = os.path.join(basepath, fname)
							with open(fpath, 'r') as f:
								content = frappe.render_template(unicode(f.read(), 'utf-8'),
									{'docs_base_url': '/assets/{app}_docs'.format(app=app)})
								content = self.make_content(content, fpath)
								title = self.make_title(basepath, fname, content)
								intro = self.make_intro(content)
								#relpath = os.path.relpath(fpath, '../apps/{app}'.format(app=app))
								self.db.sql('''insert into help(path, content, title, intro)
									values (%s, %s, %s, %s)''', (fpath, content, title, intro))

	def make_title(self, basepath, filename, html):
		if '<h1>' in html:
			title = html.split("<h1>", 1)[1].split("</h1>", 1)[0]
		elif 'index' in filename:
			title = basepath.rsplit('/', 1)[-1].title().replace("-", " ")
		else:
			title = filename.rsplit('.', 1)[0].title().replace("-", " ")
		return title

	def make_intro(self, html):
		intro = ""
		if '<p>' in html:
			intro = html.split('<p>', 1)[1].split('</p>', 1)[0]
		if 'Duration' in html:
			intro = "Help Video: " + intro
		return intro

	def make_content(self, content, path):

		html = markdown(content)

		if '{index}' in html:
			path = path.rsplit("/", 1)[0]
			index_path = os.path.join(path, "index.txt")
			if os.path.exists(index_path):
				with open(index_path, 'r') as f:
					lines = f.read().split('\n')
					links_html = "<ol class='index-links'>"
					for line in lines:
						fpath = os.path.join(path, line)
						title = line.title().replace("-", " ")
						if title:
							links_html += "<li><a data-path='{fpath}'> {title} </a></li>".format(fpath=fpath, title=title)
					links_html += "</ol>"
					html = html.replace('{index}', links_html)

		if '{next}' in html:
			html = html.replace('{next}', '')

		target = path.split('/', 3)[-1]
		app_name = path.split('/', 3)[2]
		html += '''
			<div class="page-container">
				<div class="page-content">
				<div class="edit-container text-center">
					<i class="icon icon-smile"></i>
					<a class="text-muted edit" href="https://github.com/frappe/{app_name}/blob/develop/{target}">
						Improve this page
					</a>
				</div>
				</div>
			</div>'''.format(app_name=app_name, target=target)

		soup = BeautifulSoup(html, 'html.parser')

		for link in soup.find_all('a'):
			if link.has_attr('href'):
				url = link['href']
				if '/user' in url:
					data_path = url[url.index('/user'):]
					if '.' in data_path:
						data_path = data_path[: data_path.rindex('.')]
					if data_path:
						link['data-path'] = data_path

		parent = self.get_parent(path)
		if parent:
			parent_tag = soup.new_tag('a')
			parent_tag.string = parent['title']
			parent_tag['class'] = 'parent-link'
			parent_tag['data-path'] = parent['path']
			soup.find().insert_before(parent_tag)

		return soup.prettify()

	def get_parent(self, child_path):
		path = child_path
		if 'index' in child_path:
			child_path = child_path[: child_path.rindex('index')]
		if child_path[-1] == '/':
			child_path = child_path[:-1]

		parent_path = child_path[: child_path.rindex('/')] + "/index"
		result = self.get_content(parent_path)
		if result:
			title = result[0][0]
			return { 'title': title, 'path': parent_path }
		else:
			return None

	def reorder_files(self, files):
		pos = 0
		if 'index.md' in files:
			pos = files.index('index.md')
		elif 'index.html' in files:
			pos = files.index('index.html')
		if pos:
			files[0], files[pos] = files[pos], files[0]
		return files
