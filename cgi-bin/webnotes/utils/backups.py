import webnotes

backup_folder = '/backups'
mysql_path = ''
download_folder = 'backups'

def mysqldump(db, folder=''):
	global mysql_path
	import os
	import webnotes.defs
	
	os.system('%(path)smysqldump %(db)s > %(folder)s%(db)s.sql -u %(db)s -p%(pwd)s --ignore-table=%(db)s.__DocTypeCache' % {'path':mysql_path, 'db':db, 'pwd':webnotes.defs.db_password, 'folder':folder})

def backup_db(db, conn, from_all=0):
	import os
	global backup_folder

	try:
	# Check processlist
		if from_all or len(conn.sql("show processlist")) == 1:
			p = backup_folder
			if from_all: p = backup_folder + '/dumps'	

			# clear old file
			os.system('rm %s/%s.tar.gz' % (p,db))

			# dump
			mysqldump(db, p+'/')
			
			# zip
			os.system('tar czf %s/%s.tar.gz %s/%s.sql' % (p, db, p, db))
			os.system('rm %s/%s.sql' % (p, db))
		else:
			print("Another process is running in database. Please try again")
	except Exception, e:
		#sql('unlock tables')
		raise e
		
def backup_all():
	# backups folder
	import os
	import webnotes.db
	global backup_folder
	
	conn = webnotes.db.Database(use_default=1)
	dblist = conn.sql('select db_name from tabAccount')

	# backup -all in /backups folder
	for d in (('accounts',),) + dblist:
		backup_db(d[0], conn, 1)
	
	conn.close()
	
	# dump all in /daily folder
	import time, datetime
	fname = 'daily-' + time.strftime('%Y-%m-%d') + '.tar.gz'
	
	# daily dump
	os.system('tar czf %s/daily/%s %s/dumps' % (backup_folder, fname, backup_folder))

	# keep only three files
	if len(os.listdir(backup_folder + '/daily')) > 3:
		delete_oldest_file(backup_folder + '/daily')

	# if sunday, then copy to weekly
	if datetime.datetime.now().weekday()==6:
		os.system('cp '+backup_folder+'/daily/'+fname+' '+backup_folder+'/weekly/'+fname)
	
		# keep only three files
		if len(os.listdir(backup_folder + '/weekly')) > 3:
			delete_oldest_file(backup_folder + '/weekly')
	
def delete_oldest_file(folder):
	import os
	a = sorted(os.listdir(folder), key=lambda fn: os.stat(folder+'/'+fn).st_mtime, reverse=False)
	if a:
		os.system('rm %s/%s' % (folder, a[0]))

def get_backup():
	import webnotes		
	import os, time

	global backup_folder, download_folder

	# get the last nightly backup file from the backups folder
	os.chdir(download_folder)

	if webnotes.conn.cur_db_name:
		fname = webnotes.conn.cur_db_name + '.tar.gz'

		# rename it
		from random import choice
		lnd='0123456789'
		new_name = ''.join(map(lambda x,y=lnd: choice(y), range(8))) + '.sql.gz'
		folder = backup_folder + '/dumps/'

		# get the newest file
		if os.path.exists(folder):
			os.system('cp '+ folder + webnotes.conn.cur_db_name+'.sql.gz' + ' ./' + new_name)
			webnotes.msgprint('Your nightly backup is available for download by <a href="'+download_folder+'/' + new_name + '">clicking here</a> (only for the next few hours)')
	
	# delete any files older than a day
	now = time.time()
	for f in os.listdir('.'):
		if os.stat(f).st_mtime < (now - 86400):
			if os.path.isfile(f):
				os.remove(f)
