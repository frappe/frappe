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
			self.timestamps.update(outfile)
			if verbose: print 'Wrote %s' % outfile

		return temp
		
	def changed(self, files):
		"""
			Returns true if the files are changed since last build
		"""
		import os
		from build import force_rebuild

		if force_rebuild:
			return True
		
		for f in files:
			if f in self.timestamps.dirty:
				return True
		return False

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
		self.timestamps.update(outfile)

		new_size = os.path.getsize(outfile)

		if verbose:
			print '=> %s' % outfile
			print 'Original: %.2f kB' % (org_size / 1024.0)
			print 'Compressed: %.2f kB' % (new_size / 1024.0)
			print 'Reduction: %.1f%%' % (float(org_size - new_size) / org_size * 100)

	def make(self, path):
		"""
			Build (stitch + compress) the file defined in build.json
		"""
		import os, sys, json
		from build import no_minify
		
		# open the build.json file and read
		# the dict
		bfile = open(os.path.join(path, 'build.json'), 'r')
		bdata = json.loads(bfile.read())
		bfile.close()
		
		for outfile in bdata:
			prefix, fname = False, outfile

			# check if there is a prefix
			if ':' in outfile:
				prefix, fname = outfile.split(':')

			# build the file list relative to the main folder
			fl = [os.path.relpath(os.path.join(path, f), os.curdir) for f in bdata[outfile]]

			self.timestamps.bundled += fl

			if self.changed(fl):
				# js files are minified by default unless explicitly
				# mentioned in the prefix.
				# some files may not work if minified (known jsmin bug)
				
				if fname.split('.')[-1]=='js' and prefix!='concat' and not no_minify:
					self.minify(fl, os.path.relpath(os.path.join(path, fname), os.curdir))
				else:
					self.concat(fl, os.path.relpath(os.path.join(path, fname), os.curdir))			
						
	def bundle(self, timestamps):
		"""
			Build js files from "build.json"
		"""
		import os
		self.timestamps = timestamps

		# walk the parent folder and build all files as defined in the build.json files
		for wt in os.walk('.', followlinks=True):
			if 'build.json' in wt[2]:
				# found build file
				self.make(os.path.abspath(wt[0]))

