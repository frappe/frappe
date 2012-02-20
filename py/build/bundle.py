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
				outtxt += data
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

	def make(self, bpath):
		"""
			Build (stitch + compress) the file defined in build.json
		"""
		import os, sys, json
		from build import no_minify
		
		# open the build.json file and read
		# the dict
		print "making %s ..." % bpath
		with open(bpath, 'r') as bfile:
			bdata = json.loads(bfile.read())
		
		path = os.path.dirname(bpath)
		
		for buildfile in bdata:
			# build the file list relative to the main folder
			outfile = buildfile.keys()[0]
			infiles = buildfile[outfile]
			
			fl = [os.path.relpath(os.path.join(path, f), os.curdir) for f in infiles]

			# js files are minified by default unless explicitly
			# mentioned in the prefix.
			# some files may not work if minified (known jsmin bug)
			self.concat(fl, os.path.relpath(os.path.join(path, outfile), os.curdir))			
						
		
