# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
from webnotes.utils.minify import JavascriptMinify

"""
Build the `public` folders and setup languages
"""

import os, sys, webnotes, json, shutil
from cssmin import cssmin
import webnotes.translate

def bundle(no_compress):
	"""concat / minify js files"""
	# build js files
	make_site_public_dirs()
	build(no_compress)
	webnotes.translate.clear_cache()
	
def watch(no_compress):
	"""watch and rebuild if necessary"""
	import time
	build(no_compress=True)

	while True:
		if files_dirty():
			build(no_compress=True)
		
		time.sleep(3)

def make_site_public_dirs():	
	assets_path = os.path.join(webnotes.local.sites_path, "assets")
	site_public_path = os.path.join(webnotes.local.site_path, 'public')
	for dir_path in [
			os.path.join(site_public_path, 'backups'), 
			os.path.join(site_public_path, 'files'),
			os.path.join(assets_path, 'js'), 
			os.path.join(assets_path, 'css')]:
		
		if not os.path.exists(dir_path):
			os.makedirs(dir_path)
	
	# symlink app/public > assets/app
	for app_name in webnotes.get_all_apps(True):
		pymodule = webnotes.get_module(app_name)
		source = os.path.join(os.path.abspath(os.path.dirname(pymodule.__file__)), 'public')
		target = os.path.join(assets_path, app_name)

		if not os.path.exists(target) and os.path.exists(source):
			os.symlink(os.path.abspath(source), target)

def build(no_compress=False):
	assets_path = os.path.join(webnotes.local.sites_path, "assets")

	for target, sources in get_build_maps().iteritems():
		pack(os.path.join(assets_path, target), sources, no_compress)	

	shutil.copy(os.path.join(os.path.dirname(os.path.abspath(webnotes.__file__)), 'data', 'languages.txt'), webnotes.local.sites_path)
	# reset_app_html()

def get_build_maps():
	"""get all build.jsons with absolute paths"""
	# framework js and css files
	pymodules = [webnotes.get_module(app) for app in webnotes.get_all_apps(True)]
	app_paths = [os.path.dirname(pymodule.__file__) for pymodule in pymodules]

	build_maps = {}
	for app_path in app_paths:
		path = os.path.join(app_path, 'public', 'build.json')
		if os.path.exists(path):
			with open(path) as f:
				try:
					for target, sources in json.loads(f.read()).iteritems():
						# update app path
						sources = [os.path.join(app_path, source) for source in sources]	
						build_maps[target] = sources
				except Exception, e:
					print path
					raise
		
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
				outtxt += unicode(tmpout.getvalue() or '', 'utf-8').strip('\n') + ';'
			else:
				outtxt += ('\n/*\n *\t%s\n */' % f)
				outtxt += '\n' + data + '\n'
				
		except Exception, e:
			print "--Error in:" + f + "--"
			print webnotes.get_traceback()

	if not no_compress and outtype == 'css':
		pass
		#outtxt = cssmin(outtxt)
					
	with open(target, 'w') as f:
		f.write(outtxt.encode("utf-8"))
	
	print "Wrote %s - %sk" % (target, str(int(os.path.getsize(target)/1024)))

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
	
