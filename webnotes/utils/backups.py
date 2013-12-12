# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
"""
	This module handles the On Demand Backup utility
	
	To setup in defs set: 
		backup_path: path where backups will be taken (for eg /backups)
		backup_link_path: download link for backups (eg /var/www/wnframework/backups)
		backup_url: base url of the backup folder (eg http://mysite.com/backups)
"""
#Imports
import os, webnotes
from datetime import datetime
from webnotes.utils import cstr, get_url

#Global constants
verbose = 0
from webnotes import conf
#-------------------------------------------------------------------------------
class BackupGenerator:
	"""
		This class contains methods to perform On Demand Backup
		
		To initialize, specify (db_name, user, password, db_file_name=None, db_host="localhost")
		If specifying db_file_name, also append ".sql.gz"
	"""
	def __init__(self, db_name, user, password, backup_path_db=None, backup_path_files=None, db_host="localhost"):
		self.db_host = db_host
		self.db_name = db_name
		self.user = user
		self.password = password
		self.backup_path_files = backup_path_files
		self.backup_path_db = backup_path_db

	def get_backup(self, older_than=24, ignore_files=False):
		"""
			Takes a new dump if existing file is old
			and sends the link to the file as email
		"""
		#Check if file exists and is less than a day old
		#If not Take Dump
		last_db, last_file = self.get_recent_backup(older_than)
		if not (self.backup_path_files and self.backup_path_db):
			self.set_backup_file_name()
		if not (last_db and last_file):
			self.take_dump()
			if not ignore_files:
				self.zip_files()
		else:
			self.backup_path_files = last_file
			self.backup_path_db = last_db


	def set_backup_file_name(self):
		import random
		todays_date = "".join(str(datetime.date(datetime.today())).split("-"))
		random_number = str(int(random.random()*99999999))
		
		#Generate a random name using today's date and a 8 digit random number
		for_db = todays_date + "_" + random_number + "_database.sql.gz"
		for_files = todays_date + "_" + random_number + "_files.tar"
		backup_path = get_backup_path()
		if not self.backup_path_db:
			self.backup_path_db = os.path.join(backup_path, for_db)	
		if not self.backup_path_files:
			self.backup_path_files = os.path.join(backup_path, for_files)	
		
	def get_recent_backup(self, older_than):
		file_list = os.listdir(get_backup_path())
		backup_path_files = None
		backup_path_db = None
		for this_file in file_list:
			this_file = cstr(this_file)
			this_file_path = os.path.join(get_backup_path(), this_file)
			if not is_file_old(this_file_path, older_than):
				if "_files" in this_file_path:
					backup_path_files = this_file_path
				if "_database" in this_file_path:
					backup_path_db = this_file_path
		return (backup_path_db, backup_path_files)

	def zip_files(self):
		files_path = webnotes.utils.get_site_path(conf.files_path)
		cmd_string = """tar -cf %s %s""" % (self.backup_path_files, files_path)
		err, out = webnotes.utils.execute_in_shell(cmd_string)
	
	def take_dump(self):
		import webnotes.utils
		
		# escape reserved characters
		args = dict([item[0], webnotes.utils.esc(item[1], '$ ')] 
			for item in self.__dict__.copy().items())
		cmd_string = """mysqldump -u %(user)s -p%(password)s %(db_name)s -h %(db_host)s | gzip -c > %(backup_path_db)s""" % args		
		err, out = webnotes.utils.execute_in_shell(cmd_string)
		
	def send_email(self):
		"""
			Sends the link to backup file located at erpnext/backups
		"""
		from webnotes.utils.email_lib import sendmail, get_system_managers

		recipient_list = get_system_managers()
		db_backup_url = get_url(os.path.join('backups', os.path.basename(self.backup_path_db)))
		files_backup_url = get_url(os.path.join('backups', os.path.basename(self.backup_path_files)))
		
		msg = """<p>Hello,</p>
		<p>Your backups are ready to be downloaded.</p>
		<p>1. <a href="%(db_backup_url)s">Click here to download\
		 the database backup</a></p>
		<p>2. <a href="%(files_backup_url)s">Click here to download\
		the files backup</a></p>
		<p>This link will be valid for 24 hours. A new backup will be available 
		for download only after 24 hours.</p>
		<p>Have a nice day!<br>ERPNext</p>""" % {
			"db_backup_url": db_backup_url,
			"files_backup_url": files_backup_url
		}
		
		datetime_str = datetime.fromtimestamp(os.stat(self.backup_path_db).st_ctime)
		subject = datetime_str.strftime("%d/%m/%Y %H:%M:%S") + """ - Backup ready to be downloaded"""
		
		sendmail(recipients=recipient_list, msg=msg, subject=subject)
		return recipient_list
		
		
@webnotes.whitelist()
def get_backup():
	"""
		This function is executed when the user clicks on 
		Toos > Download Backup
	"""
	#if verbose: print webnotes.conn.cur_db_name + " " + conf.db_password
	delete_temp_backups()
	odb = BackupGenerator(webnotes.conn.cur_db_name, webnotes.conn.cur_db_name,\
						  webnotes.conf.db_password, db_host = webnotes.conn.host)
	odb.get_backup()
	recipient_list = odb.send_email()
	webnotes.msgprint("""A download link to your backup will be emailed \
	to you shortly on the following email address:
	%s""" % (', '.join(recipient_list)))
	
def scheduled_backup(older_than=6, ignore_files=False, backup_path_db=None, backup_path_files=None):
	"""this function is called from scheduler
		deletes backups older than 7 days
		takes backup"""
	odb = new_backup(older_than, ignore_files, backup_path_db=backup_path_db, backup_path_files=backup_path_files)
	return odb

def new_backup(older_than=6, ignore_files=False, backup_path_db=None, backup_path_files=None):
	delete_temp_backups(older_than=168)
	odb = BackupGenerator(webnotes.conn.cur_db_name, webnotes.conn.cur_db_name,\
						  webnotes.conf.db_password, 
						  backup_path_db=backup_path_db, backup_path_files=backup_path_files, db_host = webnotes.conn.host)
	odb.get_backup(older_than, ignore_files)
	return odb

def delete_temp_backups(older_than=24):
	"""
		Cleans up the backup_link_path directory by deleting files older than 24 hours
	"""
	file_list = os.listdir(get_backup_path())
	for this_file in file_list:
		this_file_path = os.path.join(get_backup_path(), this_file)
		if is_file_old(this_file_path, older_than):
			os.remove(this_file_path)
			
def is_file_old(db_file_name, older_than=24):
		"""
			Checks if file exists and is older than specified hours
			Returns ->
			True: file does not exist or file is old
			False: file is new
		"""		
		if os.path.isfile(db_file_name):
			from datetime import timedelta
			import time
			#Get timestamp of the file
			file_datetime = datetime.fromtimestamp\
						(os.stat(db_file_name).st_ctime)
			if datetime.today() - file_datetime >= timedelta(hours = older_than):
				if verbose: print "File is old"
				return True
			else:
				if verbose: print "File is recent"
				return False
		else:
			if verbose: print "File does not exist"
			return True	

def get_backup_path():
	import os
	backup_path = webnotes.utils.get_site_path(conf.get("backup_path", "public/backups"))
	return backup_path

#-------------------------------------------------------------------------------
		
if __name__ == "__main__":
	"""
		is_file_old db_name user password db_host
		get_backup  db_name user password db_host
	"""
	import sys
	cmd = sys.argv[1]
	if cmd == "is_file_old":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] or "localhost")
		is_file_old(odb.db_file_name)
	
	if cmd == "get_backup":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] or "localhost")
		odb.get_backup()

	if cmd == "take_dump":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] or "localhost")
		odb.take_dump()
		
	if cmd == "send_email":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] or "localhost")
		odb.send_email("abc.sql.gz")
		
	if cmd == "delete_temp_backups":
		delete_temp_backups()

