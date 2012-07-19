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
import webnotes

def upload():
	form = webnotes.form

	# get record details
	dt = form.getvalue('doctype')
	dn = form.getvalue('docname')
	at_id = form.getvalue('at_id')

	webnotes.response['type'] = 'iframe'
	if not webnotes.form['filedata'].filename:
		webnotes.response['result']	= """
		<script type='text/javascript'>
		window.parent.wn.views.fomrview['%s'].frm.attachments.dialog.hide();
		window.parent.msgprint("Please select a file!");
		</script>""" % dt
		return
		
	# save
	fid, fname = save_uploaded()
	
	# save it in the form
	updated = False
	if fid:
		updated = add_file_list(dt, dn, fname, fid)
	
	if fid and updated:
		# refesh the form!
		# with the new modified timestamp
		webnotes.response['result'] = """
<script type='text/javascript'>
window.parent.wn.widgets.form.file_upload_done('%(dt)s', '%(dn)s', '%(fid)s', '%(fname)s', '%(at_id)s', '%(mod)s');
window.parent.wn.views.formview['%(dt)s'].frm.show_doc('%(dn)s');
</script>
			""" % {
				'dt': dt,
				'dn': dn,
				'fid': fid,
				'fname': fname.replace("'", "\\'"),
				'at_id': at_id,
				'mod': webnotes.conn.get_value(dt, dn, 'modified')
			}

# -------------------------------------------------------

def add_file_list(dt, dn, fname, fid):
	"""
		udpate file_list attribute of the record
	"""
	fl = webnotes.conn.get_value(dt, dn, 'file_list') or ''
	if fl:
		fl += '\n'
	
	# add new file id
	fl += fname + ',' + fid

	# save
	webnotes.conn.set_value(dt, dn, 'file_list', fl)

	return True

def remove_all(dt, dn):
	"""remove all files in a transaction"""
	file_list = webnotes.conn.get_value(dt, dn, 'file_list') or ''
	for afile in file_list.split('\n'):
		if afile:
			fname, fid = afile.split(',')
			remove_file(dt, dn, fid)

def remove_file(dt, dn, fid):
	"""Remove fid from the give file_list"""
	
	# get the old file_list
	fl = webnotes.conn.get_value(dt, dn, 'file_list') or ''
	new_fl = []
	fl = fl.split('\n')
	for f in fl:
		if f and f.split(',')[1]!=fid:
			new_fl.append(f)

	# delete
	delete_file(fid)
		
	# update the file_list
	webnotes.conn.set_value(dt, dn, 'file_list', '\n'.join(new_fl))
	
	# return the new timestamp
	return webnotes.conn.get_value(dt, dn, 'modified')

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

def get_uploaded_content():
	import webnotes
	
	if 'filedata' in webnotes.form:
		i = webnotes.form['filedata']
		webnotes.uploaded_filename, webnotes.uploaded_content = i.filename, i.file.read()
		return webnotes.uploaded_filename, webnotes.uploaded_content
	else:
		webnotes.msgprint('No File');
		return None, None

def save_uploaded():
	import webnotes.utils
	
	webnotes.response['type'] = 'iframe'

	form = webnotes.form

	fname, content = get_uploaded_content()
	if content:
		fid = save_file(fname, content)
		return fid, fname
		
	else: 
		return None, fname

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
	import os, conf

	# test size
	max_file_size = 1000000
	if hasattr(conf, 'max_file_size'):
		max_file_size = conf.max_file_size

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
		

def get_file_system_name(fname):
	# get system name from File Data table
	return webnotes.conn.sql("""select name, file_name from `tabFile Data` 
		where name=%s or file_name=%s""", (fname, fname))

def delete_file(fid, verbose=0):
	"""delete file from file system"""
	import os
	webnotes.conn.sql("delete from `tabFile Data` where name=%s", fid)	
	path = os.path.join(webnotes.get_files_path(), fid.replace('/','-'))
	if os.path.exists(path):
		os.remove(path)
		
def get_file(fname):
	f = get_file_system_name(fname)
	if f:
		file_id = f[0][0].replace('/','-')
		file_name = f[0][1]
	else:
		file_id = fname
		file_name = fname

	# read the file
	import os
	with open(os.path.join(webnotes.get_files_path(), file_id), 'r') as f:
		content = f.read()

	return [file_name, content]