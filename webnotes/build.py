# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
from webnotes.utils.minify import JavascriptMinify

"""
Build the `public` folders and setup languages
"""

import os, sys, webnotes
from cssmin import cssmin


def bundle(no_compress, cms_make=True):
	"""concat / minify js files"""
	# build js files
	check_public()
	check_lang()
	bundle = Bundle()
	bundle.no_compress = no_compress
	bundle.make()

	if cms_make:
		try:
			from startup.event_handlers import on_build
			on_build()
		except ImportError, e:
			pass
			
	clear_pyc_files()
	
def watch(no_compress):
	"""watch and rebuild if necessary"""
	import time
	bundle = Bundle()
	bundle.no_compress = no_compress

	while True:
		if bundle.dirty():
			bundle.make()
		
		time.sleep(3)

def check_public():
	from webnotes.install_lib.setup_public_folder import make
	make()

def check_lang():
	from webnotes.translate import update_translations
	update_translations()
	
def clear_pyc_files():
	from webnotes.utils import get_base_path
	for path, folders, files in os.walk(get_base_path()):
		if 'locale' in folders: folders.remove('locale')
		for f in files:
			if f.decode("utf-8").endswith(".pyc"):
				os.remove(os.path.join(path, f))
	
class Bundle:
	"""
		Concatenate, compress and mix (if required) js+css files from build.json
	"""
	no_compress = False
	timestamps = {}
	path = '.'
	
	def concat(self, filelist, outfile=None):	
		"""
			Concat css and js files into a bundle
		"""
		from cStringIO import StringIO
		
		out_type = outfile and outfile.split('.')[-1] or 'js'
		
		outtxt = ''
		for f in filelist:
			suffix = None
			if ':' in f:
				f, suffix = f.split(':')
			
			if not os.path.exists(f) or os.path.isdir(f):
				continue
			
			self.timestamps[f] = os.path.getmtime(f)
			
			# get datas
			try:
				with open(f, 'r') as infile:			
					# get file type
					ftype = f.split('.')[-1] 

					data = unicode(infile.read(), 'utf-8', errors='ignore')

				outtxt += ('\n/*\n *\t%s\n */' % f)
					
				# append
				if suffix=='concat' or out_type != 'js' or self.no_compress or ('.min.' in f):
					outtxt += '\n' + data + '\n'
				else:
					jsm = JavascriptMinify()
					tmpin = StringIO(data.encode('utf-8'))
					tmpout = StringIO()
					
					jsm.minify(tmpin, tmpout)
					tmpmin = unicode(tmpout.getvalue() or '', 'utf-8')
					tmpmin.strip('\n')
					outtxt += tmpmin
			except Exception, e:
				print "--Error in:" + f + "--"
				print webnotes.getTraceback()

		if not self.no_compress and out_type == 'css':
			outtxt = cssmin(outtxt)
						
		with open(outfile, 'w') as f:
			f.write(outtxt.encode("utf-8"))
		
		print "Wrote %s - %sk" % (outfile, str(int(os.path.getsize(outfile)/1024)))

	def dirty(self):
		"""check if build files are dirty"""

		self.make_build_data()
		for builddict in self.bdata:
			for f in self.get_infiles(builddict):

				if ':' in f:
					f, suffix = f.split(':')

				if not os.path.exists(f) or os.path.isdir(f):
					continue
				
				
				if os.path.getmtime(f) != self.timestamps.get(f):
					print f + ' dirty'
					return True
		else:
			return False

	def make(self):
		"""Build (stitch + compress) the file defined in build.json"""
						
		print "Building js and css files..."
		self.make_build_data()	
		for builddict in self.bdata:
			outfile = builddict.keys()[0]
			infiles = self.get_infiles(builddict)
			
			self.concat(infiles, os.path.relpath(os.path.join(self.path, outfile), os.curdir))
	
		self.reset_app_html()
		
	def reset_app_html(self):
		import webnotes

		if os.path.exists("public/app.html"):
			os.remove("public/app.html")
		
		splash = ""
		if os.path.exists("public/app/images/splash.svg"):
			with open("public/app/images/splash.svg") as splash_file:
				splash = splash_file.read()
		
		with open('lib/public/html/app.html', 'r') as app_html:
			data = app_html.read()
			data = data % {
				"_version_number": webnotes.generate_hash(),
				"splash": splash
			}
			with open('public/app.html', 'w') as new_app_html:
				new_app_html.write(data)
	
	def get_infiles(self, builddict):
		"""make list of files to merge"""
		outfile = builddict.keys()[0]
		infiles = builddict[outfile]
		
		# add app js and css to the list
		if outfile in self.appfiles:
			for f in self.appfiles[outfile]:
				if f not in infiles:
					infiles.append(f)
		
		fl = []
		for f in infiles:
			## load files from directory
			if f.endswith('/'):
				# add init js first
				fl += [os.path.relpath(os.path.join(f, 'init.js'), os.curdir)]
				
				# files other than init.js and beginning with "_"
				fl += [os.path.relpath(os.path.join(f, tmp), os.curdir) \
					for tmp in os.listdir(f) if (tmp != 'init.js' and not tmp.startswith('_'))]
			else:
				fl.append(os.path.relpath(os.path.join(self.path, f), os.curdir))
				
		return fl
			
	def make_build_data(self):
		"""merge build.json and lib/build.json"""
		# framework js and css files
		with open('lib/public/build.json', 'r') as bfile:
			bdata = eval(bfile.read())
		
		# app js and css files
		if os.path.exists('app/public/build.json'):
			with open('app/public/build.json', 'r') as bfile:
				appfiles = eval(bfile.read())
		else:
			appfiles = {}
		
		# add additional app files in bdata
		buildfile_list = [builddict.keys()[0] for builddict in bdata]
		for f in appfiles:
			if f not in buildfile_list:
				bdata.append({f: appfiles[f]})
		
		self.appfiles = appfiles
		self.bdata = bdata

