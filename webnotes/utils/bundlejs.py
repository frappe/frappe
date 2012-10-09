# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

from __future__ import unicode_literals
from webnotes.utils.minify import JavascriptMinify

import os, sys

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
			with open(f, 'r') as infile:			
				# get file type
				ftype = f.split('.')[-1] 

				data = infile.read()

				if os.path.basename(f)=='core.js':
					import webnotes
					data = data % {"_version_number": webnotes.generate_hash() }


			outtxt += ('\n/*\n *\t%s\n */' % f)
					
			# append
			if suffix=='concat' or out_type != 'js' or self.no_compress or ('.min.' in f):
				outtxt += '\n' + data + '\n'
			else:
				jsm = JavascriptMinify()
				tmpin = StringIO(data)
				tmpout = StringIO()
				jsm.minify(tmpin, tmpout)
				tmpmin = tmpout.getvalue() or ''
				tmpmin.strip('\n')
				outtxt += tmpmin
						
		with open(outfile, 'w') as f:
			f.write(outtxt)
		
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

def check_public():
	from webnotes.install_lib.setup_public_folder import make
	make()

def bundle(no_compress, cms_make=True):
	"""concat / minify js files"""
	# build js files
	check_public()
	bundle = Bundle()
	bundle.no_compress = no_compress
	bundle.make()

	if cms_make:
		# build index.html and app.html
		import webnotes.cms.make
		webnotes.cms.make.make()	
	
def watch(no_compress):
	"""watch and rebuild if necessary"""
	import time
	bundle = Bundle()
	bundle.no_compress = no_compress

	while True:
		if bundle.dirty():
			bundle.make()
		
		time.sleep(3)
			
