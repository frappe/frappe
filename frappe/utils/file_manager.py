# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe
import os, base64, re
import hashlib
import mimetypes
from frappe.utils import cstr, cint, get_site_path
from frappe import _
from frappe import conf

class MaxFileSizeReachedError(frappe.ValidationError): pass

def get_file_url(file_data_name):
	data = frappe.db.get_value("File Data", file_data_name, ["file_name", "file_url"], as_dict=True)
	return data.file_name or data.file_url

def upload():
	# get record details
	dt = frappe.form_dict.doctype
	dn = frappe.form_dict.docname
	file_url = frappe.form_dict.file_url
	filename = frappe.form_dict.filename
	
	if not filename and not file_url:
		frappe.msgprint(_("Please select a file or url"),
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
		return save_file(fname, content, dt, dn);
	else: 
		raise Exception

def save_url(file_url, dt, dn):
	# if not (file_url.startswith("http://") or file_url.startswith("https://")):
	# 	frappe.msgprint("URL must start with 'http://' or 'https://'")
	# 	return None, None
		
	f = frappe.get_doc({
		"doctype": "File Data",
		"file_url": file_url,
		"attached_to_doctype": dt,
		"attached_to_name": dn
	})
	f.ignore_permissions = True
	try:
		f.insert();
	except frappe.DuplicateEntryError:
		return frappe.get_doc("File Data", f.duplicate_entry)		
	return f

def get_uploaded_content():	
	# should not be unicode when reading a file, hence using frappe.form
	if 'filedata' in frappe.form_dict:
		frappe.uploaded_content = base64.b64decode(frappe.form_dict.filedata)
		frappe.uploaded_filename = frappe.form_dict.filename
		return frappe.uploaded_filename, frappe.uploaded_content
	else:
		frappe.msgprint('No File')
		return None, None

def extract_images_from_html(doc, fieldname):
	content = doc.get(fieldname)
	frappe.flags.has_dataurl = False
	
	def _save_file(match):
		data = match.group(1)
		headers, content = data.split(",")
		filename = headers.split("filename=")[-1]
		filename = save_file(filename, content, doc.doctype, doc.name, decode=True).get("file_name")
		if not frappe.flags.has_dataurl:
			frappe.flags.has_dataurl = True
		
		return '<img src="{filename}"'.format(filename = filename)
	
	if content:
		content = re.sub('<img\s*src=\s*["\'](data:[^"\']*)["\']', _save_file, content)
		if frappe.flags.has_dataurl:
			doc.set(fieldname, content)
			
def save_file(fname, content, dt, dn, decode=False):
	if decode:
		if isinstance(content, unicode):
			content = content.encode("utf-8")
		content = base64.b64decode(content)

	file_size = check_max_file_size(content)
	content_hash = get_content_hash(content)
	content_type = mimetypes.guess_type(fname)[0]

	method = (webnotes.get_hooks().get('write_file'))
	if method:
		method = webnotes.get_attr(method[0])
	else:
		method = save_file_on_filesystem
	file_path = method(fname, content, content_hash, content_type=content_type)

	f = webnotes.bean({
		"doctype": "File Data",
		"file_name": file_path,
		"attached_to_doctype": dt,
		"attached_to_name": dn,
		"file_size": file_size,
		"file_hash": content_hash
	})
	f.ignore_permissions = True
	try:
		f.insert();
	except webnotes.DuplicateEntryError:
		return webnotes.doc("File Data", f.doc.duplicate_entry)

	return f.doc
	
def save_file_on_filesystem(fname, content, content_hash, content_type=None):
	import filecmp
	from frappe.modules import load_doctype_module
	files_path = os.path.join(frappe.local.site_path, "public", "files")
	module = load_doctype_module(dt, frappe.db.get_value("DocType", dt, "module"))
	
	temp_fname = write_file(content, files_path)
	fname = scrub_file_name(fname)

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
				fpath = os.path.join(files_path, fname)
				found_match = True
				break
				
		if not found_match:
			# get_new_version name
			fname = get_new_fname_based_on_version(files_path, main, extn, versions)
			fpath = os.path.join(files_path, fname)
			
			# rename
			if os.path.exists(fpath.encode("utf-8")):
				frappe.throw("File already exists: " + fname)
				
			os.rename(temp_fname, fpath.encode("utf-8"))
	else:
		fpath = os.path.join(files_path, fname)
		
		# rename new file
		if os.path.exists(fpath.encode("utf-8")):
			frappe.throw("File already exists: " + fname)
		
		os.rename(temp_fname, fpath.encode("utf-8"))
	return  os.path.relpath(fpath, 
			get_site_path(conf.get("public_path", "public")))

def get_file_versions(files_path, main, extn):
	out = []
	for f in os.listdir(files_path):
		f = cstr(f)
		if f.startswith(main) and f.endswith(extn):
			out.append(f)
	return out

def get_new_fname_based_on_version(files_path, main, extn, versions):
	versions.sort()
	if "-" in versions[-1]:
		version = cint(versions[-1].split("-")[-1]) or 1
	else:
		version = 1
	
	new_fname = main + "-" + str(version) + "." + extn
	while os.path.exists(os.path.join(files_path, new_fname).encode("utf-8")):
		version += 1
		new_fname = main + "-" + str(version) + "." + extn
		if version > 100:
			frappe.msgprint("Too many versions", raise_exception=True)
			
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
		frappe.msgprint(_("File size exceeded the maximum allowed size"),
			raise_exception=MaxFileSizeReachedError)
			
	return file_size

def write_file(content, files_path):
	"""write file to disk with a random name (to compare)"""
	# create account folder (if not exists)
	frappe.create_folder(files_path)
	fname = os.path.join(files_path, frappe.generate_hash())

	# write the file
	with open(fname, 'w+') as f:
		f.write(content)

	return fname	

def remove_all(dt, dn):
	"""remove all files in a transaction"""
	try:
		for fid in frappe.db.sql_list("""select name from `tabFile Data` where
			attached_to_doctype=%s and attached_to_name=%s""", (dt, dn)):
			remove_file(fid)
	except Exception, e:
		if e.args[0]!=1054: raise # (temp till for patched)

def remove_file(fid):
	"""Remove file and File Data entry"""
	frappe.delete_doc("File Data", fid)

def delete_file_data_content(path):
	method = (frappe.get_hooks().get('delete_file_data_content'))
	if method:
		method = frappe.get_attr(method[0])
	else:
		method = delete_file_from_filesystem
	method(path)

def delete_file_from_filesystem(path):
	if path.startswith("files/"):
		path = frappe.utils.get_site_path("public", self.doc.file_name)
	else:
		path = frappe.utils.get_site_path("public", "files", self.doc.file_name)
	if os.path.exists(path):
		os.remove(path)
		
def get_file(fname):
	f = frappe.db.sql("""select file_name from `tabFile Data` 
		where name=%s or file_name=%s""", (fname, fname))
	if f:
		file_name = f[0][0]
	else:
		file_name = fname
		
	if not "/" in file_name:
		file_name = "files/" + file_name
	
	# read the file	
	with open(get_site_path("public", file_name), 'r') as f:
		content = f.read()

	return [file_name, content]

def get_content_hash(content):
	return hashlib.md5(content).hexdigest()

def get_file_url(file_data_doc):
	if file_data_doc.file_url:
		return file_url

	method = (webnotes.get_hooks().get('get_file_data_url'))
	if method:
		method = webnotes.get_attr(method[0])
		return method(file_data_doc.file_name)
	else:
		return file_name

