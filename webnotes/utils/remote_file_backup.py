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
import os
import webnotes

def upload_to_dropbox():
	from dropbox import client, rest, session
	from conf import dropbox_access_key, dropbox_secret_key
	
	from webnotes.utils.backups import new_backup
	print "Taking backup..."
	webnotes.connect()
	backup = new_backup()
	filename = backup.backup_path_db
	print os.path.basename(filename)
	
	print "Starting session..."
	sess = session.DropboxSession(dropbox_access_key, dropbox_secret_key, "app_folder")

	sess.set_token('rl8hpbk775mb77b','snmegusva4jt9t2')
	client = client.DropboxClient(sess)
	size = os.stat(filename).st_size
	f = open(filename,'r')
	
	# create folder
	print "Creating folder..."
	try:
		client.file_create_folder("erpnext")
	except rest.ErrorResponse, e:
		if e.status!=403:
			raise e
		
	
	if size > 4194304:
		print "Uploading (chunked)..."
		uploader = client.get_chunked_uploader(f, size)
		while uploader.offset < size:
			try:
				uploader.upload_chunked()
			except rest.ErrorResponse, e:
				pass
	else:
		print "Uploading..."
		response = client.put_file('erpnext/' + os.path.basename(filename), f, overwrite=True)


if __name__=="__main__":
	upload_to_dropbox()
	
	