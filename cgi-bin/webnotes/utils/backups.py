"""
	This module handles the On Demand Backup utility	
"""
#Imports
import os, webnotes
from datetime import datetime


#Global constants
from webnotes.defs import backup_path, backup_link_path, backup_url
verbose = 0

class BackupGenerator:
	"""
		This class contains methods to perform On Demand Backup
		
		To initialize, specify (db_name, user, password, db_file_name=None)
		If specifying db_file_name, also append ".sql.gz"
	"""
	def __init__(self, db_name, user, password, db_file_name=None):
		self.db_name = db_name
		self.user = user
		self.password = password
		self.db_file_name = db_file_name and db_file_name \
							or (backup_path + db_name + ".sql.gz")

	def take_dump(self):
		"""
			Dumps a db via mysqldump
		"""
		os.system("""mysqldump -u %(user)s -p%(password)s %(db_name)s | 
					 gzip -c > %(db_file_name)s""" % self.__dict__)
	
	
	def copy_to_backup_link(self):
		"""
			Copies the backup file from backup path to shared link path
			It also gives the file a random name, thus hiding the db_name
		"""
		import random
		todays_date = "".join(str(datetime.date(datetime.today())).split("-"))
		random_number = str(int(random.random()*99999999))
		
		#Generate a random name using today's date and a 8 digit random number
		random_name = todays_date + "_" + random_number + ".sql.gz"
		
		os.system("""cp -f %(src_file)s %(dest_file)s""" % \
					{"src_file":self.db_file_name,
					 "dest_file":(backup_link_path + random_name)})
		if verbose: print "file copied"
		return random_name
	
	
	def get_recipients(self):
		"""
			Get recepient's email address
		"""
		import webnotes.db
		webnotes.conn = webnotes.db.Database(use_default = 1)
		recipient_list = webnotes.conn.sql("""SELECT parent FROM tabUserRole
							 WHERE role='System Manager'
							 AND parent!='Administrator'""")
		return [i[0] for i in recipient_list]
		
		
	def send_email(self, backup_file):
		"""
			Sends the link to backup file located at erpnext/backups
		"""
		file_url = backup_url + backup_file
		from webnotes.utils.email_lib import sendmail
		
		recipient_list = self.get_recipients()
		msg = """<a href=%(file_url)s>Click here to begin downloading\
		 your backup</a>
		 
		 This link will be valid for 24 hours.
		 
		 Also, a new backup will be available for download (if requested)\
		  only after 24 hours.""" % {"file_url":file_url}
		
		datetime_str = datetime.fromtimestamp(os.stat(self.db_file_name).st_ctime)
		
		subject = datetime_str.strftime("%d/%m/%Y %H:%M:%S") + """ - Backup ready to be downloaded"""
		sendmail(recipients=recipient_list, msg=msg, subject=subject)
		
		
		
	def get_backup(self):
		"""
			Takes a new dump if existing file is old
			and sends the link to the file as email
		"""
		#Check if file exists and is less than a day old
		#If not Take Dump
		if is_file_old(self.db_file_name):
			self.take_dump()
					
		#Copy file to backup_link_path
		#This is a security hole. When the user calls get_backup repeatedly
		#a file will be generated each time.
		backup_file = self.copy_to_backup_link()		

		#Email Link
		self.send_email(backup_file)
		

def get_backup():
	"""
		This function is executed when the user clicks on 
		Toos > Download Backup
	"""
	#if verbose: print webnotes.conn.cur_db_name + " " + webnotes.defs.db_password
	odb = BackupGenerator(webnotes.conn.cur_db_name, webnotes.conn.cur_db_name,\
						 webnotes.defs.db_password)
	odb.get_backup()
	webnotes.msgprint("""A download link to your backup will be emailed \
	to you shortly.""")


def delete_temp_backups():
	"""
		Cleans up the backup_link_path directory by deleting files older than 24 hours
	"""
	file_list = os.listdir(backup_link_path)
	for this_file in file_list:
		this_file_path = backup_link_path + this_file
		if is_file_old(this_file_path, 1):
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
