# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes
import os
from webnotes.utils import cstr, cint, get_storage_path
from webnotes import _
from webnotes import conf

class MaxFileSizeReachedError(webnotes.ValidationError): pass

def upload():
	# get record details
	dt = webnotes.form_dict.doctype
	dn = webnotes.form_dict.docname
	file_url = webnotes.form_dict.file_url
	filename = webnotes.form_dict.filename
	
	if not filename and not file_url:
		webnotes.msgprint(_("Please select a file or url"),
			raise_exception=True)

	# save
	if filename:
		filedata = save_uploaded(dt, dn)
	elif file_url:
		filedata = save_url(file_url, dt, dn)
		
	return {"fid": filedata.name, "filename": filedata.file_name or filedata.file_url }

def save_uploaded(dt, dn):
	fname, content = get_uploaded_content()
	if content:
		return save_file(fname, content, dt, dn)
	else: 
		raise Exception

def save_url(file_url, dt, dn):
	if not (file_url.startswith("http://") or file_url.startswith("https://")):
		webnotes.msgprint("URL must start with 'http://' or 'https://'")
		return None, None
		
	f = webnotes.bean({
		"doctype": "File Data",
		"file_url": file_url,
		"attached_to_doctype": dt,
		"attached_to_name": dn
	})
	f.ignore_permissions = True
	f.insert();
	return f.doc

def get_uploaded_content():	
	# should not be unicode when reading a file, hence using webnotes.form
	if 'filedata' in webnotes.form_dict:
		import base64
		webnotes.uploaded_content = base64.b64decode(webnotes.form_dict.filedata)
		webnotes.uploaded_filename = webnotes.form_dict.filename
		return webnotes.uploaded_filename, webnotes.uploaded_content
	else:
		webnotes.msgprint('No File')
		return None, None

def save_file(fname, content, dt, dn):
	import filecmp
	from webnotes.model.code import load_doctype_module
	files_path = get_storage_path(conf.public_path)
	module = load_doctype_module(dt, webnotes.conn.get_value("DocType", dt, "module"))
	
	if hasattr(module, "attachments_folder"):
		files_path = os.path.join(files_path, module.attachments_folder)

	file_size = check_max_file_size(content)
	temp_fname = write_file(content, files_path)
	fname = scrub_file_name(fname)
	fpath = os.path.join(files_path, fname)

	fname_parts = fname.split(".", -1)
	main = ".".join(fname_parts[:-1])
	extn = fname_parts[-1]
	versions = get_file_versions(files_path, main, extn)
	
	if versions:
		found_match = False
		for version in versions:
			if filecmp.cmp(os.path.join(files_path, version), temp_fname):
				# remove new file, already exists!
				os.remove(temp_fname)
				fname = version
				found_match = True
				break
				
		if not found_match:
			# get_new_version name
			fname = get_new_fname_based_on_version(files_path, main, extn, versions)
			
			# rename
			os.rename(temp_fname, os.path.join(files_path, fname))
	else:
		# rename new file
		os.rename(temp_fname, os.path.join(files_path, fname))

	f = webnotes.bean({
		"doctype": "File Data",
		"file_name": os.path.relpath(os.path.join(files_path, fname), get_storage_path(conf.public_path)),
		"attached_to_doctype": dt,
		"attached_to_name": dn,
		"file_size": file_size
	})
	f.ignore_permissions = True
	f.insert();

	return f.doc

def get_file_versions(files_path, main, extn):
	return filter(lambda f: f.startswith(main) and f.endswith(extn), os.listdir(files_path))

def get_new_fname_based_on_version(files_path, main, extn, versions):
	versions.sort()
	if "-" in versions[-1]:
		version = cint(versions[-1].split("-")[-1]) or 1
	else:
		version = 1
	
	new_fname = main + "-" + str(version) + "." + extn
	while os.path.exists(os.path.join(files_path, new_fname)):
		version += 1
		new_fname = main + "-" + str(version) + "." + extn
		if version > 100:
			webnotes.msgprint("Too many versions", raise_exception=True)
			
	return new_fname

def scrub_file_name(fname):		
	if '\\' in fname:
		fname = fname.split('\\')[-1]
	if '/' in fname:
		fname = fname.split('/')[-1]
	return fname
	
def check_max_file_size(content):
	max_file_size = conf.get('max_file_size') or 1000000
	file_size = len(content)

	if file_size > max_file_size:
		webnotes.msgprint(_("File size exceeded the maximum allowed size"),
			raise_exception=MaxFileSizeReachedError)
			
	return file_size

def write_file(content, files_path):
	"""write file to disk with a random name (to compare)"""
	# create account folder (if not exists)
	webnotes.create_folder(files_path)
	fname = os.path.join(files_path, webnotes.generate_hash())

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
		
def get_file(fname):
	f = webnotes.conn.sql("""select file_name from `tabFile Data` 
		where name=%s or file_name=%s""", (fname, fname))
	if f:
		file_name = f[0][0]
	else:
		file_name = fname

	# read the file
	import os
	files_path = get_storage_path(conf.files_path)
	file_path = os.path.join(files_path, file_name)
	if not os.path.exists(file_path):
		# check in folders
		for basepath, folders, files in os.walk(files_path):
			if file_name in files:
				file_path = os.path.join(basepath, file_name)
				break
		
	with open(file_path, 'r') as f:
		content = f.read()

	return [file_name, content]
