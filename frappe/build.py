# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
from frappe.utils.minify import JavascriptMinify
import warnings

from six import iteritems, text_type
import subprocess
from distutils.spawn import find_executable

"""
Build the `public` folders and setup languages
"""

import os, frappe, json, shutil, re

app_paths = None
def setup():
	global app_paths
	pymodules = []
	for app in frappe.get_all_apps(True):
		try:
			pymodules.append(frappe.get_module(app))
		except ImportError: pass
	app_paths = [os.path.dirname(pymodule.__file__) for pymodule in pymodules]

def get_node_pacman():
	pacmans = ['yarn', 'npm']
	for exec_ in pacmans:
		exec_ = find_executable(exec_)
		if exec_:
			return exec_
	raise ValueError('No Node.js Package Manager found.')

def bundle(no_compress, app=None, make_copy=False, restore=False, verbose=False):
	"""concat / minify js files"""
	setup()
	make_asset_dirs(make_copy=make_copy, restore=restore)

	pacman = get_node_pacman()
	mode = 'build' if no_compress else 'production'
	command = '{pacman} run {mode}'.format(pacman=pacman, mode=mode)

	if app:
		command += ' --app {app}'.format(app=app)

	frappe_app_path = os.path.abspath(os.path.join(app_paths[0], '..'))
	check_yarn()
	frappe.commands.popen(command, cwd=frappe_app_path)

def watch(no_compress):
	"""watch and rebuild if necessary"""
	setup()

	pacman = get_node_pacman()

	frappe_app_path = os.path.abspath(os.path.join(app_paths[0], '..'))
	check_yarn()
	frappe_app_path = frappe.get_app_path('frappe', '..')
	frappe.commands.popen('{pacman} run watch'.format(pacman=pacman), cwd = frappe_app_path)

def check_yarn():
	from distutils.spawn import find_executable
	if not find_executable('yarn'):
		print('Please install yarn using below command and try again.')
		print('npm install -g yarn')
		return

def make_asset_dirs(make_copy=False, restore=False):
	# don't even think of making assets_path absolute - rm -rf ahead.
	assets_path = os.path.join(frappe.local.sites_path, "assets")
	for dir_path in [
			os.path.join(assets_path, 'js'),
			os.path.join(assets_path, 'css')]:

		if not os.path.exists(dir_path):
			os.makedirs(dir_path)

	for app_name in frappe.get_all_apps(True):
		pymodule = frappe.get_module(app_name)
		app_base_path = os.path.abspath(os.path.dirname(pymodule.__file__))

		symlinks = []
		# app/public > assets/app
		symlinks.append([os.path.join(app_base_path, 'public'), os.path.join(assets_path, app_name)])
		# app/node_modules > assets/app/node_modules
		symlinks.append([os.path.join(app_base_path, '..', 'node_modules'), os.path.join(assets_path, app_name, 'node_modules')])

		app_doc_path = None
		if os.path.isdir(os.path.join(app_base_path, 'docs')):
			app_doc_path = os.path.join(app_base_path, 'docs')

		elif os.path.isdir(os.path.join(app_base_path, 'www', 'docs')):
			app_doc_path = os.path.join(app_base_path, 'www', 'docs')

		if app_doc_path:
			symlinks.append([app_doc_path, os.path.join(assets_path, app_name + '_docs')])

		for source, target in symlinks:
			source = os.path.abspath(source)
			if os.path.exists(source):
				if restore:
					if os.path.exists(target):
						if os.path.islink(target):
							os.unlink(target)
						else:
							shutil.rmtree(target)
						shutil.copytree(source, target)
				elif make_copy:
					if os.path.exists(target):
						warnings.warn('Target {target} already exists.'.format(target = target))
					else:
						shutil.copytree(source, target)
				else:
					if os.path.exists(target):
						if os.path.islink(target):
							os.unlink(target)
						else:
							shutil.rmtree(target)
					os.symlink(source, target)
			else:
				# warnings.warn('Source {source} does not exist.'.format(source = source))
				pass

def build(no_compress=False, verbose=False):
	assets_path = os.path.join(frappe.local.sites_path, "assets")

	for target, sources in iteritems(get_build_maps()):
		pack(os.path.join(assets_path, target), sources, no_compress, verbose)

def get_build_maps():
	"""get all build.jsons with absolute paths"""
	# framework js and css files

	build_maps = {}
	for app_path in app_paths:
		path = os.path.join(app_path, 'public', 'build.json')
		if os.path.exists(path):
			with open(path) as f:
				try:
					for target, sources in iteritems(json.loads(f.read())):
						# update app path
						source_paths = []
						for source in sources:
							if isinstance(source, list):
								s = frappe.get_pymodule_path(source[0], *source[1].split("/"))
							else:
								s = os.path.join(app_path, source)
							source_paths.append(s)

						build_maps[target] = source_paths
				except ValueError as e:
					print(path)
					print('JSON syntax error {0}'.format(str(e)))
	return build_maps

timestamps = {}

def pack(target, sources, no_compress, verbose):
	from six import StringIO

	outtype, outtxt = target.split(".")[-1], ''
	jsm = JavascriptMinify()

	for f in sources:
		suffix = None
		if ':' in f: f, suffix = f.split(':')
		if not os.path.exists(f) or os.path.isdir(f):
			print("did not find " + f)
			continue
		timestamps[f] = os.path.getmtime(f)
		try:
			with open(f, 'r') as sourcefile:
				data = text_type(sourcefile.read(), 'utf-8', errors='ignore')

			extn = f.rsplit(".", 1)[1]

			if outtype=="js" and extn=="js" and (not no_compress) and suffix!="concat" and (".min." not in f):
				tmpin, tmpout = StringIO(data.encode('utf-8')), StringIO()
				jsm.minify(tmpin, tmpout)
				minified = tmpout.getvalue()
				if minified:
					outtxt += text_type(minified or '', 'utf-8').strip('\n') + ';'

				if verbose:
					print("{0}: {1}k".format(f, int(len(minified) / 1024)))
			elif outtype=="js" and extn=="html":
				# add to frappe.templates
				outtxt += html_to_js_template(f, data)
			else:
				outtxt += ('\n/*\n *\t%s\n */' % f)
				outtxt += '\n' + data + '\n'

		except Exception:
			print("--Error in:" + f + "--")
			print(frappe.get_traceback())

	with open(target, 'w') as f:
		f.write(outtxt.encode("utf-8"))

	print("Wrote %s - %sk" % (target, str(int(os.path.getsize(target)/1024))))

def html_to_js_template(path, content):
	'''returns HTML template content as Javascript code, adding it to `frappe.templates`'''
	return """frappe.templates["{key}"] = '{content}';\n""".format(\
		key=path.rsplit("/", 1)[-1][:-5], content=scrub_html_template(content))

def scrub_html_template(content):
	'''Returns HTML content with removed whitespace and comments'''
	# remove whitespace to a single space
	content = re.sub("\s+", " ", content)

	# strip comments
	content =  re.sub("(<!--.*?-->)", "", content)

	return content.replace("'", "\'")

def files_dirty():
	for target, sources in iteritems(get_build_maps()):
		for f in sources:
			if ':' in f: f, suffix = f.split(':')
			if not os.path.exists(f) or os.path.isdir(f): continue
			if os.path.getmtime(f) != timestamps.get(f):
				print(f + ' dirty')
				return True
	else:
		return False

def compile_less():
	from distutils.spawn import find_executable
	if not find_executable("lessc"):
		return

	for path in app_paths:
		less_path = os.path.join(path, "public", "less")
		if os.path.exists(less_path):
			for fname in os.listdir(less_path):
				if fname.endswith(".less") and fname != "variables.less":
					fpath = os.path.join(less_path, fname)
					mtime = os.path.getmtime(fpath)
					if fpath in timestamps and mtime == timestamps[fpath]:
						continue

					timestamps[fpath] = mtime

					print("compiling {0}".format(fpath))

					css_path = os.path.join(path, "public", "css", fname.rsplit(".", 1)[0] + ".css")
					os.system("lessc {0} > {1}".format(fpath, css_path))
