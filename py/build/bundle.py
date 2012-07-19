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
from minify import JavascriptMinify

class Bundle:
	"""
		Concatenate, compress and mix (if required) js+css files from build.json
	"""	
	def concat(self, filelist, outfile=None):	
		"""
			Concat css and js files into a bundle
		"""
		import os
		from cStringIO import StringIO
		from build import verbose
		
		out_type = outfile and outfile.split('.')[-1] or 'js'
		
		outtxt = ''
		for f in filelist:
			suffix = None
			if ':' in f:
				f, suffix = f.split(':')
			
			# print f + ' | ' + str(int(os.path.getsize(f)/1024)) + 'k'
			
			# get data
			with open(f, 'r') as infile:			
				# get file type
				ftype = f.split('.')[-1] 

				data = infile.read()

				# css -> js
				if out_type=='js' and ftype =='css':
					data = "\nwn.assets.handler.css('%s');\n" %\
					 	data.replace("'", "\\'").replace('\n', '\\\n')

			outtxt += ('\n/*\n *\t%s\n */' % f)
					
			# append
			if suffix=='concat' or out_type != 'js':
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

	def make(self):
		"""
			Build (stitch + compress) the file defined in build.json
		"""
		import os, sys
		from build import no_minify
		
		# open the build.json file and read
		# the dict
		
		print "Building js and css files..."
		
		# framework js and css files
		with open('lib/build.json', 'r') as bfile:
			bdata = eval(bfile.read())
		
		# app js and css files
		if os.path.exists('build.json'):
			with open('build.json', 'r') as bfile:
				appfiles = eval(bfile.read())
		else:
			appfiles = {}
		
		path = '.'
		
		# add additional app files in bdata
		buildfile_list = [buildfile.keys()[0] for buildfile in bdata]
		for f in appfiles:
			if f not in buildfile_list:
				bdata.append({f: appfiles[f]})		
		
		for buildfile in bdata:
			# build the file list relative to the main folder
			outfile = buildfile.keys()[0]
			infiles = buildfile[outfile]
			
			# add app js and css to the list
			if outfile in appfiles:
				for f in appfiles[outfile]:
					if f not in infiles:
						infiles.append(f)
			
			fl = [os.path.relpath(os.path.join(path, f), os.curdir) for f in infiles]

			# js files are minified by default unless explicitly
			# mentioned in the prefix.
			# some files may not work if minified (known jsmin bug)
			self.concat(fl, os.path.relpath(os.path.join(path, outfile), os.curdir))						
		
