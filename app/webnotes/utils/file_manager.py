import webnotes

def save_as_attachment():
	form = webnotes.form

	# get record details
	dt = form.getvalue('doctype')
	dn = form.getvalue('docname')
	at_id = form.getvalue('at_id')

	# extract file from the upload handler
	from webnotes.utils.upload_handler import UploadHandler
	uh = UploadHandler()
	if not uh.file_name:
		# something went wrong, quit
		return
	# save
	fid = save_file(uh.file_name, uh.content)
	
	uh.set_callback('''
		window.parent.wn.widgets.form.file_upload_done('%s', '%s', '%s', '%s', '%s');
		window.parent.frms['%s'].show_doc('%s');
		''' % (dt, dn, fid, uh.file_name.replace("'", "\\'"), at_id, dt, dn))

def make_thumbnail(blob, size):
	"""
		Use PIL to res-size incoming image
	"""
	from PIL import Image
	import cStringIO
				
	fobj = cStringIO.StringIO(blob)
	image = Image.open(fobj)
	image.thumbnail((tn,tn*2), Image.ANTIALIAS)
	outfile = cStringIO.StringIO()
	image.save(outfile, 'JPEG')
	outfile.seek(0)
	fcontent = outfile.read()
	
	return fcontent


# -------------------------------------------------------

def save_file(fname, content, module=None):
	from webnotes.model.doc import Document

	# some browsers return the full path
	if '\\' in fname:
		fname = fname.split('\\')[-1]
	if '/' in fname:
		fname = fname.split('/')[-1]

	# generate the ID (?)
	f = Document('File Data')
	f.file_name = fname
	if module:
		f.module = module
	f.save(1)
	
	write_file(f.name, content)

	return f.name

# -------------------------------------------------------

def write_file(fid, content):
	import os, webnotes.defs

	# test size
	max_file_size = 1000000
	if hasattr(webnotes.defs, 'max_file_size'):
		max_file_size = webnotes.defs.max_file_size

	if len(content) > max_file_size:
		raise Exception, 'Maximum File Limit (%s MB) Crossed' % (int(max_file_size / 1000000))

	# no slashes
	fid = fid.replace('/','-')

	# save to a folder (not accessible to public)
	folder = webnotes.get_files_path()
		
	# create account folder (if not exists)
	webnotes.create_folder(folder)

	# write the file
	file = open(os.path.join(folder, fid),'w+')
	file.write(content)
	file.close()
		

# -------------------------------------------------------
def get_file_system_name(fname):
	"""
		Get filesystem name by id or name
	"""
	return webnotes.conn.sql("select name, file_name from `tabFile Data` where name=%s or file_name=%s", (fname, fname))

# -------------------------------------------------------
def delete_file(fname, verbose=0):
	import os
		
	for f in get_file_system_name(fname):
		webnotes.conn.sql("delete from `tabFile Data` where name=%s", f[0])
	
		# delete file
		file_id = f[0].replace('/','-')
		try:
			os.remove(os.path.join(webnotes.get_files_path(), file_id))
		except OSError, e:
			if e.args[0]!=2:
				raise e
		
		if verbose: webnotes.msgprint('File Deleted')

# Get File
# -------------------------------------------------------

def get_file(fname):
	in_fname = fname
	
	# from the "File" table
	if webnotes.conn.exists('File',fname):
		fname = webnotes.conn.sql("select file_list from tabFile where name=%s", fname)
		fname = fname and fname[0][0]
		fname = fname.split('\n')[0].split(',')[1]


	if get_file_system_name(fname):
		f = get_file_system_name(fname)[0]
	else:
		f = None
	return [f[1], get_file_content(f[0])]

def get_file_content(fid):
	"""
		Return file content by id
	"""
	# read the file
	import os
		
	file_id = fid.replace('/','-')
	file = open(os.path.join(webnotes.get_files_path(), file_id), 'r')
	content = file.read()
	file.close()
	return content

def convert_to_files(verbose=0):
	"""
		Deprecated: marked for deletion
	"""	
	# nfiles
	fl = webnotes.conn.sql("select name from `tabFile Data`")
	for f in fl:
		# get the blob
		blob = webnotes.conn.sql("select blob_content from `tabFile Data` where name=%s", f[0])[0][0]
		
		if blob:

			if hasattr(blob, 'tostring'):
				blob = blob.tostring()

			# write the file
			write_file(f[0], blob)
						
			if verbose:
				webnotes.msgprint('%s updated' % f[0])

"""
	Get / set file attachments on a document.
	
	Example to reset the user profile image::

		from webnotes.model.file_manager import FileAttachments
	
		fa = FileAttachments('Profile', session['user'])
		fa.delete_all()
		fa.add(uh.file_name, uh.content)
		fa.save()
		
"""
class FileAttachments:
	def __init__(self, dt, dn):
		self.dt, self.dn = dt, dn
		self.al = webnotes.conn.get_value(dt, dn, 'file_list')
		self.al = self.al and self.al.split('\n') or []
	
	def get_fid(self, idx):
		"""
			return file id for index
		"""
		return self.al[idx].split(',')[1]

	def get_file(self, idx):
		"""
			Return the attachment
		"""
		return get_file_content(self.get_fid(idx))
		
	def delete_file(self, idx):
		"""
			Delete an attachment
		"""
		delete_file(self.get_fid(idx))
	
	def delete_all(self):
		"""
			delete all attachments
		"""
		for i in range(len(self.al)):
			self.delete_file(i)
		self.al = []
		
	def add(self, fname, content=None, fid=None):
		"""
			Add a new attachment and update
		"""
		if content:
			# save the file
			fid = save_file(fname, content)

		self.al.append(fname+','+fid)
		
	def save(self):
		"""
			Save attachment to the doc
		"""
		webnotes.conn.set_value(self.dt, self.dn, 'file_list', '\n'.join(self.al))