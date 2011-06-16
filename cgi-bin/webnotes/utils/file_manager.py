def upload():
	import webnotes
	form = webnotes.form

	# get record details
	dt = form.get('doctype')
	dn = form.get('docname')
	at_id = form.get('at_id')

	# save
	fid, fname = save_uploaded()
	
	if fid:
		# refesh the form!
		webnotes.response['result'] = """
<script type='text/javascript'>
window.parent.wn.widgets.form.file_upload_done('%s', '%s', '%s', '%s', '%s');
window.parent.frms['%s'].show_doc('%s');
</script>
			""" % (dt, dn, fid, fname.replace("'", "\\'"), at_id, dt, dn)

# -------------------------------------------------------

def make_thumbnail(blob, size):
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


def save_uploaded(js_okay='window.parent.msgprint("File Upload Successful")', js_fail=''):
	import webnotes
	import webnotes.utils
	
	webnotes.response['type'] = 'iframe'

	form, fid, fname = webnotes.form, None, None

	try:
		# has attachment?
		if 'filedata' in form:
			i = form['filedata']
	
			fname, content = i.filename, i.file.read()
	
			# thumbnail
			if webnotes.form.get('thumbnail'):
				try:
					content = make_thumbnail(content, int(form.get('thumbnail')))
					# change extension to jpg
					fname = '.'.join(fname.split('.')[:-1])+'.jpg'
				except Exception, e:
					pass
		
			# get the file id
			fid = save_file(fname, content)
			
			# okay
			webnotes.response['result'] = """<script type='text/javascript'>%s</script>""" % js_okay
		else:
			webnotes.response['result'] = """<script type='text/javascript'>window.parent.msgprint("No file"); %s</script>""" % js_fail
			
	except Exception, e:
		webnotes.response['result'] = """<script type='text/javascript'>window.parent.msgprint("%s"); window.parent.errprint("%s"); %s</script>""" % (str(e), webnotes.utils.getTraceback().replace('\n','<br>').replace('"', '\\"'), js_fail)
	
	return fid, fname

# -------------------------------------------------------

def save_file(fname, content, module=None):
	import webnotes
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
	import webnotes, os, webnotes.defs

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
	# get system name from File Data table
	import webnotes
	return webnotes.conn.sql("select name, file_name from `tabFile Data` where name=%s or file_name=%s", (fname, fname))

# -------------------------------------------------------
def delete_file(fname, verbose=0):
	import webnotes, os
		
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
	import webnotes
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

		
	# read the file
	import os
		
	file_id = f[0].replace('/','-')
	file = open(os.path.join(webnotes.get_files_path(), file_id), 'r')
	content = file.read()
	file.close()
	return [f[1], content]

# Conversion Patch
# -------------------------------------------------------

def convert_to_files(verbose=0):
	import webnotes
	
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

# -------------------------------------------------------
