# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
from frappe.utils.minify import JavascriptMinify

"""
Build the `public` folders and setup languages
"""

import os, frappe, json, shutil, re
# from cssmin import cssmin


app_paths = None
def setup():
	global app_paths
	pymodules = []
	for app in frappe.get_all_apps(True):
		try:
			pymodules.append(frappe.get_module(app))
		except ImportError: pass
	app_paths = [os.path.dirname(pymodule.__file__) for pymodule in pymodules]

def bundle(no_compress, make_copy=False, verbose=False):
	"""concat / minify js files"""
	# build js files
	setup()

	make_asset_dirs(make_copy=make_copy)
	build(no_compress, verbose)

def watch(no_compress):
	"""watch and rebuild if necessary"""
	setup()

	import time
	compile_less()
	build(no_compress=True)

	while True:
		compile_less()
		if files_dirty():
			build(no_compress=True)

		time.sleep(3)

def make_asset_dirs(make_copy=False):
	assets_path = os.path.join(frappe.local.sites_path, "assets")
	for dir_path in [
			os.path.join(assets_path, 'js'),
			os.path.join(assets_path, 'css')]:

		if not os.path.exists(dir_path):
			os.makedirs(dir_path)

	# symlink app/public > assets/app
	for app_name in frappe.get_all_apps(True):
		pymodule = frappe.get_module(app_name)
		source = os.path.join(os.path.abspath(os.path.dirname(pymodule.__file__)), 'public')
		target = os.path.join(assets_path, app_name)

		if not os.path.exists(target) and os.path.exists(source):
			if make_copy:
				shutil.copytree(os.path.abspath(source), target)
			else:
				os.symlink(os.path.abspath(source), target)

def build(no_compress=False, verbose=False):
	assets_path = os.path.join(frappe.local.sites_path, "assets")

	for target, sources in get_build_maps().iteritems():
		pack(os.path.join(assets_path, target), sources, no_compress, verbose)

	shutil.copy(os.path.join(os.path.dirname(os.path.abspath(frappe.__file__)), 'data', 'languages.txt'), frappe.local.sites_path)
	# reset_app_html()

def get_build_maps():
	"""get all build.jsons with absolute paths"""
	# framework js and css files

	build_maps = {}
	for app_path in app_paths:
		path = os.path.join(app_path, 'public', 'build.json')
		if os.path.exists(path):
			with open(path) as f:
				try:
					for target, sources in json.loads(f.read()).iteritems():
						# update app path
						source_paths = []
						for source in sources:
							if isinstance(source, list):
								s = frappe.get_pymodule_path(source[0], *source[1].split("/"))
							else:
								s = os.path.join(app_path, source)
							source_paths.append(s)

						build_maps[target] = source_paths
				except Exception:
					print path
					raise

	return build_maps

timestamps = {}

def pack(target, sources, no_compress, verbose):
	from cStringIO import StringIO

	outtype, outtxt = target.split(".")[-1], ''
	jsm = JavascriptMinify()

	for f in sources:
		suffix = None
		if ':' in f: f, suffix = f.split(':')
		if not os.path.exists(f) or os.path.isdir(f):
			print "did not find " + f
			continue
		timestamps[f] = os.path.getmtime(f)
		try:
			with open(f, 'r') as sourcefile:
				data = unicode(sourcefile.read(), 'utf-8', errors='ignore')

			extn = f.rsplit(".", 1)[1]

			if outtype=="js" and extn=="js" and (not no_compress) and suffix!="concat" and (".min." not in f):
				tmpin, tmpout = StringIO(data.encode('utf-8')), StringIO()
				jsm.minify(tmpin, tmpout)
				minified = tmpout.getvalue()
				if minified:
					outtxt += unicode(minified or '', 'utf-8').strip('\n') + ';'

				if verbose:
					print "{0}: {1}k".format(f, int(len(minified) / 1024))
			elif outtype=="js" and extn=="html":
				# add to frappe.templates
				outtxt += html_to_js_template(f, data)
			else:
				outtxt += ('\n/*\n *\t%s\n */' % f)
				outtxt += '\n' + data + '\n'

		except Exception:
			print "--Error in:" + f + "--"
			print frappe.get_traceback()

	if not no_compress and outtype == 'css':
		pass
		#outtxt = cssmin(outtxt)

	with open(target, 'w') as f:
		f.write(outtxt.encode("utf-8"))

	print "Wrote %s - %sk" % (target, str(int(os.path.getsize(target)/1024)))

def html_to_js_template(path, content):
	# remove whitespace to a single space
	content = re.sub("\s+", " ", content)

	# strip comments
	content =  re.sub("(<!--.*?-->)", "", content)

	return """frappe.templates["{key}"] = '{content}';\n""".format(\
		key=path.rsplit("/", 1)[-1][:-5], content=content.replace("'", "\'"))

def files_dirty():
	for target, sources in get_build_maps().iteritems():
		for f in sources:
			if ':' in f: f, suffix = f.split(':')
			if not os.path.exists(f) or os.path.isdir(f): continue
			if os.path.getmtime(f) != timestamps.get(f):
				print f + ' dirty'
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

					print "compiling {0}".format(fpath)

					css_path = os.path.join(path, "public", "css", fname.rsplit(".", 1)[0] + ".css")
					os.system("lessc {0} > {1}".format(fpath, css_path))
