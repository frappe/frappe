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


#Global constants
verbose = 0
import conf
#-------------------------------------------------------------------------------
class BackupGenerator:
	"""
		This class contains methods to perform On Demand Backup
		
		To initialize, specify (db_name, user, password, db_file_name=None)
		If specifying db_file_name, also append ".sql.gz"
	"""
	def __init__(self, db_name, user, password):
		self.db_name = db_name
		self.user = user
		self.password = password
		self.backup_file_name = self.get_backup_file_name()
		self.backup_file_path = os.path.join(conf.backup_path, self.backup_file_name)
	
	def get_backup_file_name(self):
		import random
		todays_date = "".join(str(datetime.date(datetime.today())).split("-"))
		random_number = str(int(random.random()*99999999))
		
		#Generate a random name using today's date and a 8 digit random number
		random_name = todays_date + "_" + random_number + ".sql.gz"
		return random_name
	
	def take_dump(self):
		"""
			Dumps a db via mysqldump
		"""
		import webnotes.utils
		
		# escape reserved characters
		args = dict([item[0], webnotes.utils.esc(item[1], '$ ')] 
			for item in self.__dict__.copy().items())

		cmd_string = "mysqldump -u %(user)s -p%(password)s %(db_name)s | gzip -c > %(backup_file_path)s" \
			% args

		ret = os.system(cmd_string)
	
	def get_recipients(self):
		"""
			Get recepient's email address
		"""
		#import webnotes.db
		#webnotes.conn = webnotes.db.Database(use_default=1)
		recipient_list = webnotes.conn.sql(\
				   """SELECT parent FROM tabUserRole 
					  WHERE role='System Manager' 
					  AND parent!='Administrator' 
					  AND parent IN 
							 (SELECT email FROM tabProfile WHERE enabled=1)""")
		return [i[0] for i in recipient_list]
		
		
	def send_email(self, backup_file):
		"""
			Sends the link to backup file located at erpnext/backups
		"""
		backup_url = webnotes.conn.get_value('Website Settings',
			'Website Settings', 'subdomain') or ''
		backup_url = os.path.join('http://' + backup_url, 'backups')
		file_url = os.path.join(backup_url, backup_file)
		from webnotes.utils.email_lib import sendmail
		
		recipient_list = self.get_recipients()
		msg = """<a href="%(file_url)s">Click here to begin downloading\
		 your backup</a>
		 
		 This link will be valid for 24 hours.
		 
		 Also, a new backup will be available for download (if requested)\
		  only after 24 hours.""" % {"file_url":file_url}
		
		backup_file_path = os.path.join(conf.backup_path, backup_file)
		datetime_str = datetime.fromtimestamp(os.stat(backup_file_path).st_ctime)
		
		subject = datetime_str.strftime("%d/%m/%Y %H:%M:%S") + """ - Backup ready to be downloaded"""
		sendmail(recipients=recipient_list, msg=msg, subject=subject)
		return recipient_list
		
		
	def get_backup(self):
		"""
			Takes a new dump if existing file is old
			and sends the link to the file as email
		"""
		#Check if file exists and is less than a day old
		#If not Take Dump
		backup_file = recent_backup_exists()

		if not backup_file:
			self.take_dump()
			backup_file = self.backup_file_name
		
		#Email Link
		recipient_list = self.send_email(backup_file)

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
						  webnotes.get_db_password(webnotes.conn.cur_db_name))
	recipient_list = odb.get_backup()
	webnotes.msgprint("""A download link to your backup will be emailed \
	to you shortly on the following email address:
	%s""" % (', '.join(recipient_list)))

def recent_backup_exists():
	file_list = os.listdir(conf.backup_path)
	for this_file in file_list:
		this_file_path = os.path.join(conf.backup_path, this_file)
		if not is_file_old(this_file_path):
			return this_file
	return None

def delete_temp_backups():
	"""
		Cleans up the backup_link_path directory by deleting files older than 24 hours
	"""
	file_list = os.listdir(conf.backup_path)
	for this_file in file_list:
		this_file_path = os.path.join(conf.backup_path, this_file)
		if is_file_old(this_file_path):
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

#-------------------------------------------------------------------------------
		
if __name__ == "__main__":
	"""
		is_file_old db_name user password
		get_backup  db_name user password
	"""
	import sys
	cmd = sys.argv[1]
	if cmd == "is_file_old":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4])
		is_file_old(odb.db_file_name)
	
	if cmd == "get_backup":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4])
		odb.get_backup()

	if cmd == "take_dump":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4])
		odb.take_dump()
		
	if cmd == "send_email":
		odb = BackupGenerator(sys.argv[2], sys.argv[3], sys.argv[4])
		odb.send_email("abc.sql.gz")
		
	if cmd == "delete_temp_backups":
		delete_temp_backups()

