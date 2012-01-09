from minify import JavascriptMinify

class Bundle:
	"""
		Concatenate, compress and mix (if required) js+css files from build.json
	"""	
	def concat(self, filelist, outfile=None,  is_js=False):	
		"""
			Concat css and js files into a bundle
		"""
		import os
		from cStringIO import StringIO
		from build import verbose
		
		out_type = outfile and outfile.split('.')[-1] or 'js'
		
		temp = StringIO()
		for f in filelist:
			if verbose:
				print f + ' | ' + str(int(os.path.getsize(f)/1024)) + 'k'

			fh = open(f)
			
			# get file type
			ftype = f.split('.')[-1] 

			# special concat (css inside js)
			if is_js and ftype =='css':
				css = fh.read()
				data = "\nwn.assets.handler.css('%s');\n" % css.replace("'", "\\'").replace('\n', '\\\n')

			# plain concat
			else:
				data = fh.read() + '\n'
				
			fh.close()
			temp.write(data)
					
		if outfile:
			f = open(outfile, 'w')
			f.write(temp.getvalue())
			f.close()

			if verbose: print 'Wrote %s' % outfile

		return temp

	def minify(self, in_files, outfile, concat=False):
		"""
			Compress in_files into outfile,
			give some stats
		"""
		from build import verbose
		import os

		# concat everything into temp
		outtype = outfile.split('.')[-1]
		temp = self.concat(in_files, is_js=True)
	
		out = open(outfile, 'w')

		org_size = len(temp.getvalue())
		temp.seek(0)

		# minify
		jsm = JavascriptMinify()
		jsm.minify(temp, out)

		out.close()

		new_size = os.path.getsize(outfile)

		if verbose:
			print '=> %s' % outfile
			print 'Original: %.2f kB' % (org_size / 1024.0)
			print 'Compressed: %.2f kB' % (new_size / 1024.0)
			print 'Reduction: %.1f%%' % (float(org_size - new_size) / org_size * 100)

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
		
		for outfile in bdata:
			prefix, fname = False, outfile

			# check if there is a prefix
			if ':' in outfile:
				prefix, fname = outfile.split(':')

			# build the file list relative to the main folder
			fl = [os.path.relpath(os.path.join(path, f), os.curdir) for f in bdata[outfile]]

			# js files are minified by default unless explicitly
			# mentioned in the prefix.
			# some files may not work if minified (known jsmin bug)
				
			if fname.split('.')[-1]=='js' and prefix!='concat' and not no_minify:
				self.minify(fl, os.path.relpath(os.path.join(path, fname), os.curdir))
			else:
				self.concat(fl, os.path.relpath(os.path.join(path, fname), os.curdir))			
						
		
