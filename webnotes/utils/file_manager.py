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
import os, conf
from webnotes.utils import cstr, get_path
from webnotes import _

class MaxFileSizeReachedError(webnotes.ValidationError): pass

def upload():
	# get record details
	dt = webnotes.form_dict.doctype
	dn = webnotes.form_dict.docname
	at_id = webnotes.form_dict.at_id
	file_url = webnotes.form_dict.file_url
	filename = webnotes.form['filedata'].filename
	
	webnotes.response['type'] = 'iframe'
	if not filename and not file_url:
		webnotes.response['result']	= """
		<script type='text/javascript'>
		window.parent.wn.views.fomrview['%s'].frm.attachments.dialog.hide();
		window.parent.msgprint("Please upload a file or copy-paste a link (http://...)");
		</script>""" % dt
		return
		
	# save
	if filename:
		fid, fname = save_uploaded(dt, dn)
	elif file_url:
		fid, fname = save_url(file_url, dt, dn)

	if fid:
		# refesh the form!
		# with the new modified timestamp
		webnotes.response['result'] = """
<script type='text/javascript'>
window.parent.wn.ui.form.file_upload_done('%(dt)s', '%(dn)s', '%(fid)s', '%(fname)s', '%(at_id)s', '%(mod)s');
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

def save_uploaded(dt, dn):	
	webnotes.response['type'] = 'iframe'
	fname, content = get_uploaded_content()
	if content:
		fid = save_file(fname, content, dt, dn)
		return fid, fname
	else: 
		raise Exception

def save_url(file_url, dt, dn):
	if not (file_url.startswith("http://") or file_url.startswith("https://")):
		webnotes.msgprint("URL must start with 'http://' or 'https://'")
		return None, None
		
	f = webnotes.doc("File Data")
	f.file_url = file_url
	f.file_name = file_url.split('/')[-1]
	f.attached_to_doctype = dt
	f.attached_to_name = dn
	f.save(new=1)
	return f.name, file_url

def get_uploaded_content():	
	# should not be unicode when reading a file, hence using webnotes.form
	if 'filedata' in webnotes.form:
		i = webnotes.form['filedata']
		webnotes.uploaded_filename, webnotes.uploaded_content = cstr(i.filename), i.file.read()
		return webnotes.uploaded_filename, webnotes.uploaded_content
	else:
		webnotes.msgprint('No File')
		return None, None

def save_file(fname, content, dt, dn):
	from filecmp import cmp
	files_path = get_files_path()

	file_size = check_max_file_size(content)
	temp_fname = write_file(content)
	fname = scrub_file_name(fname)	
	fpath = os.path.join(files_path, fname)
	
	if os.path.exists(fpath):
		if cmp(fpath, temp_fname):
			# remove new file, already exists!
			os.remove(temp_fname)
		else:
			# get_new_version name
			fname = get_new_fname_based_on_version(file_path, fname)
			
			# rename
			os.rename(temp_fname, os.path.join(files_path, fname))
	else:
		# rename new file
		os.rename(temp_fname, os.path.join(files_path, fname))

	f = webnotes.doc('File Data')
	f.file_name = fname
	f.attached_to_doctype = dt
	f.attached_to_name = dn
	f.fize_size = file_size
	f.save(1)

	return f.name

def get_new_fname_based_on_version(files_path, fname):
	# new version of the file is being uploaded, add a revision number?
	versions = filter(lambda f: f.startswith(fname), os.listdir(files_path))

	versions.sort()
	if "-" in versions[-1]:
		version = int(versions.split("-")[-1]) or 1
	else:
		version = 1
	
	new_fname = fname + "-" + str(version)
	while os.path.exists(os.path.join(files_path, new_fname)):
		version += 1
		new_fname = fname + "-" + str(version)
		if version > 100:
			break # let there be an exception
			
	return new_fname

def scrub_file_name(fname):
	if '\\' in fname:
		fname = fname.split('\\')[-1]
	if '/' in fname:
		fname = fname.split('/')[-1]
	return fname
	
def check_max_file_size(content):
	max_file_size = getattr(conf, 'max_file_size', 1000000)
	file_size = len(content)

	if file_size > max_file_size:
		webnotes.msgprint(_("File size exceeded the maximum allowed size"),
			raise_exception=MaxFileSizeReachedError)
			
	return file_size

def write_file(content):
	"""write file to disk with a random name (to compare)"""
	# create account folder (if not exists)
	webnotes.create_folder(get_files_path())
	fname = os.path.join(get_files_path(), webnotes.generate_hash())

	# write the file
	with open(fname, 'w+') as f:
		f.write(content)

	return fname	

def remove_all(dt, dn):
	"""remove all files in a transaction"""
	try:
		for fid in webnotes.conn.sql_list("""select name from `tabFile Data` where
			attached_to_doctype=%s and attached_to_name=%s""", (dt, dn)):
			remove_file(fid)
	except Exception, e:
		if e.args[0]!=1054: raise e # (temp till for patched)

def remove_file(fid):
	"""Remove file and File Data entry"""	
	webnotes.delete_doc("File Data", fid)
		
def get_file_system_name(fname):
	# get system name from File Data table
	return webnotes.conn.sql("""select name, file_name from `tabFile Data` 
		where name=%s or file_name=%s""", (fname, fname))
		
def get_file(fname):
	f = get_file_system_name(fname)
	if f:
		file_name = f[0][1]
	else:
		file_name = fname

	# read the file
	import os
	with open(os.path.join(get_files_path(), file_name), 'r') as f:
		content = f.read()

	return [file_name, content]

files_path = None
def get_files_path():
	global files_path
	if not files_path:
		files_path = get_path("public", "files")
	return files_path
