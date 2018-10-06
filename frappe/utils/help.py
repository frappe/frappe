# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals, print_function

import io
import frappe
import hashlib

import os, subprocess
import jinja2.exceptions
from bs4 import BeautifulSoup

def sync():
	# make table
	print('Syncing help database...')
	help_db = HelpDatabase()
	help_db.make_database()
	help_db.connect()
	help_db.make_table()
	help_db.sync_pages()
	help_db.build_index()

@frappe.whitelist()
def get_help(text):
	return HelpDatabase().search(text)

@frappe.whitelist()
def get_installed_app_help(text):
	return HelpDatabase().app_docs_search(text)

@frappe.whitelist()
def get_help_content(path):
	return HelpDatabase().get_content(path)

def get_improve_page_html(app_name, target):
	docs_config = frappe.get_module(app_name + ".config.docs")
	source_link = docs_config.source_link
	branch = getattr(docs_config, "branch", "develop")
	html = '''<div class="page-container">
				<div class="page-content">
				<div class="edit-container text-center">
					<i class="fa fa-smile text-muted"></i>
					<a class="edit text-muted" href="{source_link}/blob/{branch}/{target}">
						Improve this page
					</a>
				</div>
				</div>
			</div>'''.format(source_link=source_link, app_name=app_name, target=target, branch=branch)
	return html


class HelpDatabase(object):
	def __init__(self):
		self.global_help_setup = frappe.conf.get('global_help_setup')
		if self.global_help_setup:
			bench_name = os.path.basename(os.path.abspath(frappe.get_app_path('frappe')).split('/apps/')[0])
			self.help_db_name = 'd' + hashlib.sha224(bench_name.encode('utf-8')).hexdigest()[:15]

	def make_database(self):
		'''make database for global help setup'''
		if not self.global_help_setup:
			return
		frappe.database.setup_help_database(self.help_db_name)


	def connect(self):
		if self.global_help_setup:
			self.db = frappe.database.get_db(user=self.help_db_name, password=self.help_db_name)
		else:
			self.db = frappe.db

	def make_table(self):
		if not 'help' in self.db.get_tables():
			self.db.create_help_table()

	def search(self, words):
		self.connect()
		return self.db.sql('''
			select title, intro, path from help where title like %s union
			select title, intro, path from help where match(content) against (%s) limit 10''', ('%'+words+'%', words))

	def app_docs_search(self, words):
		self.connect()
		frappe_path = '%' + 'apps/frappe' + '%'
		return self.db.sql('''
			select
				title, intro, full_path
			from
				help
			where
				title like %s
				and
				full_path not like %s

			union

			select
				title, intro, full_path
			from
				help
			where
				match(content) against (%s)
				and
				full_path not like %s
			limit
				10

		''', ('%'+words+'%', frappe_path, words, frappe_path))

	def get_content(self, path):
		self.connect()
		query = '''SELECT `title`, `content`
			FROM `help`
			WHERE `path` LIKE '{path}%'
			ORDER BY `path` DESC
			LIMIT 1'''
		result = None

		if not path.endswith('index'):
			result = self.db.sql(query.format(path=os.path.join(path, 'index')))

		if not result:
			result = self.db.sql(query.format(path=path))

		return {'title':result[0][0], 'content':result[0][1]} if result else {}

	def sync_pages(self):
		self.db.sql('truncate help')
		doc_contents = '<ol>'
		apps = os.listdir('../apps') if self.global_help_setup else frappe.get_installed_apps()

		for app in apps:
			# Expect handling of cloning docs apps in bench
			docs_app = frappe.get_hooks('docs_app', app, app)[0]

			web_folder = 'www/' if docs_app != app else ''

			docs_folder = '../apps/{docs_app}/{docs_app}/{web_folder}docs/user'.format(
				docs_app=docs_app, web_folder=web_folder)
			self.out_base_path = '../apps/{docs_app}/{docs_app}/{web_folder}docs'.format(
				docs_app=docs_app, web_folder=web_folder)
			if os.path.exists(docs_folder):
				app_name = getattr(frappe.get_module(app), '__title__', None) or app.title()
				doc_contents += '<li><a data-path="/{app}/index">{app_name}</a></li>'.format(
					app=app, app_name=app_name)

				for basepath, folders, files in os.walk(docs_folder):
					files = self.reorder_files(files)
					for fname in files:
						if fname.rsplit('.', 1)[-1] in ('md', 'html'):
							fpath = os.path.join(basepath, fname)
							with io.open(fpath, 'r', encoding = 'utf-8') as f:
								try:
									content = frappe.render_template(f.read(),
										{'docs_base_url': '/assets/{docs_app}_docs'.format(docs_app=docs_app)})

									relpath = self.get_out_path(fpath)
									relpath = relpath.replace("user", app)
									content = frappe.utils.md_to_html(content)
									title = self.make_title(basepath, fname, content)
									intro = self.make_intro(content)
									content = self.make_content(content, fpath, relpath, app, docs_app)
									self.db.sql('''INSERT INTO `help`(`path`, `content`, `title`, `intro`, `full_path`)
										VALUES (%s, %s, %s, %s, %s)''', (relpath, content, title, intro, fpath))
								except jinja2.exceptions.TemplateSyntaxError:
									print("Invalid Jinja Template for {0}. Skipping".format(fpath))

		doc_contents += "</ol>"
		self.db.sql('''insert into help(path, content, title, intro, full_path) values (%s, %s, %s, %s, %s)''',
			('/documentation/index', doc_contents, 'Documentation', '', ''))


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

	def make_content(self, html, path, relpath, app_name, doc_app):
		if '<h1>' in html:
			html = html.split('</h1>', 1)[1]

		if '{next}' in html:
			html = html.replace('{next}', '')

		soup = BeautifulSoup(html, 'html.parser')

		self.fix_links(soup, app_name)
		self.fix_images(soup, doc_app)

		parent = self.get_parent(relpath)
		if parent:
			parent_tag = soup.new_tag('a')
			parent_tag.string = parent['title']
			parent_tag['class'] = 'parent-link'
			parent_tag['data-path'] = parent['path']
			soup.find().insert_before(parent_tag)

		return soup.prettify()

	def fix_links(self, soup, app_name):
		for link in soup.find_all('a'):
			if link.has_attr('href'):
				url = link['href']
				if '/user' in url:
					data_path = url[url.index('/user'):]
					if '.' in data_path:
						data_path = data_path[: data_path.rindex('.')]
					if data_path:
						link['data-path'] = data_path.replace("user", app_name)

	def fix_images(self, soup, app_name):
		for img in soup.find_all('img'):
			if img.has_attr('src'):
				url = img['src']
				if '/docs/' in url:
					img['src'] = url.replace('/docs/', '/assets/{0}_docs/'.format(app_name))

	def build_index(self):
		for data in self.db.sql('select path, full_path, content from help'):
			self.make_index(data[0], data[1], data[2])

	def make_index(self, original_path, full_path, content):
		'''Make index from index.txt'''
		if '{index}' in content:
			path = os.path.dirname(full_path)
			files = []

			# get files from index.txt
			index_path = os.path.join(path, "index.txt")
			if os.path.exists(index_path):
				with open(index_path, 'r') as f:
					files = f.read().splitlines()

			# files not in index.txt
			for f in os.listdir(path):
				if not os.path.isdir(os.path.join(path, f)) and len(f.rsplit('.', 1)) == 2:
					name, extn = f.rsplit('.', 1)
					if name not in files \
						and name != 'index' and extn in ('md', 'html'):
						files.append(name)

			links_html = "<ol class='index-links'>"
			for line in files:
				fpath = os.path.join(os.path.dirname(original_path), line)

				title = self.db.sql('select title from help where path like %s',
					os.path.join(fpath, 'index') + '%')
				if not title:
					title = self.db.sql('select title from help where path like %s',
						fpath + '%')

				if title:
					title = title[0][0]
					links_html += "<li><a data-path='{fpath}'> {title} </a></li>".format(
						fpath=fpath, title=title)
				# else:
				#	bad entries in .txt files
				# 	print fpath

			links_html += "</ol>"
			html = content.replace('{index}', links_html)

			self.db.sql('update help set content=%s where path=%s', (html, original_path))

	def get_out_path(self, path):
		return '/' + os.path.relpath(path, self.out_base_path)

	def get_parent(self, child_path):
		if 'index' in child_path:
			child_path = child_path[: child_path.rindex('index')]
		if child_path[-1] == '/':
			child_path = child_path[:-1]
		child_path = child_path[: child_path.rindex('/')]

		out = None
		if child_path:
			parent_path = child_path + "/index"
			out = self.get_content(parent_path)
		#if parent is documentation root
		else:
			parent_path = "/documentation/index"
			out = {}
			out['title'] = "Documentation"

		if not out:
			return None

		out['path'] = parent_path
		return out

	def reorder_files(self, files):
		pos = 0
		if 'index.md' in files:
			pos = files.index('index.md')
		elif 'index.html' in files:
			pos = files.index('index.html')
		if pos:
			files[0], files[pos] = files[pos], files[0]
		return files

def setup_apps_for_docs(app):
	docs_app = frappe.get_hooks('docs_app', app, app)[0]

	if docs_app and not os.path.exists(frappe.get_app_path(app)):
		print("Getting {docs_app} required by {app}".format(docs_app=docs_app, app=app))
		subprocess.check_output(['bench', 'get-app', docs_app], cwd = '..')
	else:
		if docs_app:
			print("{docs_app} required by {app} already present".format(docs_app=docs_app, app=app))
