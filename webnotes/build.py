# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
from webnotes.utils.minify import JavascriptMinify

"""
Build the `public` folders and setup languages
"""

import os, sys, webnotes, json
from cssmin import cssmin

def bundle():
	"""concat / minify js files"""
	# build js files
	make_site_public_dirs()
	check_lang()
	build()
	
def watch(no_compress):
	"""watch and rebuild if necessary"""
	import time
	build(no_compress=True)

	while True:
		if files_dirty():
			build_js_css_packs()
		
		time.sleep(3)

def make_site_public_dirs():
	webnotes.init()
	
	for dirs in ['backups', 'files', 'js', 'css']:
		dir_path = os.path.join('public', dirs)
		if not os.path.exists(dir_path):
			os.makedirs(dir_path)
	
	for app in webnotes.get_app_list():
		pymodule = webnotes.get_module(app)
		pymodule_public_path = os.path.join(os.path.abspath(os.path.dirname(pymodule.__file__)), 'public')

		if not os.path.exists(app) and os.path.exists(pymodule_public_path):
			os.symlink(pymodule_public_path, app)
			
def check_lang():
	from webnotes.translate import update_translations
	update_translations()
	
def clear_pyc_files():
	from webnotes.utils import get_base_path
	for path, folders, files in os.walk(get_base_path()):
		for dontwalk in ('locale', '.git', 'public'):
			if dontwalk in folders: 
				folders.remove(dontwalk)
			
		for f in files:
			if f.decode("utf-8").endswith(".pyc"):
				os.remove(os.path.join(path, f))

def build(no_compress=False):
	build_maps = get_build_maps()

	for target in build_maps:
		pack(target, build_maps[target], no_compress)	

	self.reset_app_html()

def get_build_maps():
	"""get all build.jsons with absolute paths"""
	# framework js and css files
	pymodules = [webnotes.get_module(app) for app in webnotes.get_app_list(True)]
	app_paths = [os.path.dirname(pymodule.__file__) for pymodule in pymodules]

	build_maps = {}
	for app_path in app_paths:
		path = os.path.join(app_path, 'public', 'build.json')
		if os.path.exists(path):
			with open(path) as f:
				ret = {}
				for target, sources in bdata.iteritems():
					# update app path
					sources = [os.path.join(app_path, source) for source in sources]	
					build_maps[target] = sources
	
	return build_maps

timestamps = {}

def pack(target, sources, no_compress):
	from cStringIO import StringIO
	
	outtype, outtxt = target.split(".")[-1], ''
	jsm = JavascriptMinify()
	
	for f in sources:
		suffix = None
		if ':' in f: f, suffix = f.split(':')
		if not os.path.exists(f) or os.path.isdir(f): continue
		timestamps[f] = os.path.getmtime(f)
		try:
			with open(f, 'r') as sourcefile:			
				data = unicode(sourcefile.read(), 'utf-8', errors='ignore')
			
			if outtype=="js" and (not no_compress) and suffix!="concat" and (".min." not in f):
				tmpin, tmpout = StringIO(data.encode('utf-8')), StringIO()
				jsm.minify(tmpin, tmpout)
				outtxt += unicode(tmpout.getvalue() or '', 'utf-8').strip('\n')
			else:
				outtxt += ('\n/*\n *\t%s\n */' % f)
				outtxt += '\n' + data + '\n'
				
		except Exception, e:
			print "--Error in:" + f + "--"
			print webnotes.getTraceback()

	if not no_compress and out_type == 'css':
		outtxt = cssmin(outtxt)
					
	with open(outfile, 'w') as f:
		f.write(outtxt.encode("utf-8"))
	
	print "Wrote %s - %sk" % (outfile, str(int(os.path.getsize(outfile)/1024)))

def files_dirty():
	for target, sources in build_maps.iteritems():
		for f in sources:
			if ':' in f: f, suffix = f.split(':')
			if not os.path.exists(f) or os.path.isdir(f): continue
			if os.path.getmtime(f) != timestamps.get(f):
				print f + ' dirty'
				return True
	else:
		return False

		
	# def reset_app_html(self):
	# 	import webnotes
	# 
	# 	app_html_path = os.path.join(self.path, 'app.html')
	# 	if os.path.exists(app_html_path):
	# 		os.remove(app_html_path)
	# 	
	# 	# splash_path = os.path.join(self.path, )
	# 	# splash = ""
	# 	# if os.path.exists("public/app/images/splash.svg"):
	# 	# 	with open("public/app/images/splash.svg") as splash_file:
	# 	# 		splash = splash_file.read()
	# 	# 
	# 	# with open('lib/public/html/app.html', 'r') as app_html:
	# 	# 	data = app_html.read()
	# 	# 	data = data % {
	# 	# 		"_version_number": webnotes.generate_hash(),
	# 	# 		"splash": splash
	# 	# 	}
	# 		with open(app_html_path, 'w') as new_app_html:
	# 			new_app_html.write(data)
	
