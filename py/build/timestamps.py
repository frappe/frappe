class Timestamps:
	"""
		Build / manage json timestamp files
	"""
	previous = {}
	dirty = []
	bundled = []
	current = {}
	ignore_hidden = True
	ignore_extn = ('pyc', 'DS_Store', 'gitignore')
	"""
		load timestamps and dirty files
	"""
	def __init__(self):
		self.load()
		self.get_current()
		self.check_dirty()
		
	def check_dirty(self):
		"""
			Returns true if the current folder is dirty
		"""
		from build import verbose
		
		import os
		self.dirty = []

		if not self.previous:
				if verbose:
					print 'Dirty: no timestamps!'
					self.dirty = self.current.keys()
		else:
			# check both ways for missing files
			
			for f in self.current:
				if  self.current[f] != self.previous.get(f):
					print '**** %s changed | %s -> %s' % (f, self.previous.get(f), self.current.get(f))
					self.dirty.append(f)

			for f in self.previous:
				if  self.previous[f] != self.current.get(f):
					if f not in self.dirty:
						print '**** %s changed | %s -> %s' % (f, self.previous.get(f), self.current.get(f))
						self.dirty.append(f)
		
		# unique
		self.dirty = list(set(self.dirty))

	def get_current(self):
		"""
			build timestamps dict for specified files
		"""
		try:
			import config.assets
		except ImportError:
			return self.get_current_from_folders()
			
		ts = {}
		for fname in config.assets.file_list:
			ts[fname] = str(int(os.stat(fname).st_mtime))
		
		self.current = ts
			

	def get_current_from_folders(self):
		"""
			walk in all folders and build tree of all js, css, html, md files
		"""
		import os
		ts = {}

		# walk the parent folder and build all files as defined in the build.json files
		for wt in os.walk('.', followlinks=True):				
			# build timestamps
			if self.ignore_hidden:
				for d in wt[1]:
					if d.startswith('.'):
						wt[1].remove(d)
					if os.path.exists(os.path.join(wt[0], d, '.no_timestamps')):
						wt[1].remove(d)

			for f in wt[2]:
				if f.split('.')[-1] not in self.ignore_extn and f!='_timestamps.js':
					fname = os.path.relpath(os.path.join(wt[0], f), os.curdir)
					ts[fname] = str(int(os.stat(fname).st_mtime))
	
		self.current = ts

						
	def write(self):
		"""
			Write timestamp if dirty
		"""
		import json, os
		
		ts_path = 'config/_timestamps.js'

		# write timestamps
		f = open(ts_path, 'w')
		self.get_current()
		f.write(json.dumps(self.current))
		f.close()
				
	def load(self):
		"""
			Get all timestamps from file			
		"""
		from build import verbose
		import json, os
		
		ts_path = os.path.join('config', '_timestamps.js')
		if os.path.exists(ts_path):
			ts = open(ts_path, 'r')		
			# merge the timestamps
			tmp = json.loads(ts.read())
			ts.close()
		else:
			if verbose:
				print "** No timestamps **"
			tmp = {}
		
		self.previous = tmp
	
	def update(self, fname):
		"""
			Update timestamp of the given file and add to dirty
		"""
		import os
		self.current[fname] = str(int(os.stat(fname).st_mtime))
		self.dirty.append(fname)
	
	def get(self, rettype='dict', types=[]):
		"""
			return timestamps (ignore the ones not wanted)
		"""
		# remove all .md timestamps
		ret = {}
		for t in self.current:
			if t.split('.')[-1] in types:
				if t not in self.bundled:
					ret[t] = self.current[t]
		
		if rettype=='dict':
			return ret
		else:
			import json
			return json.dumps(ret)