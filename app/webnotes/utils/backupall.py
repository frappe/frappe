import os

# go to current directory
os.chdir(__file__[:-12])

import webnotes.utils.backups

webnotes.utils.backups.backup_all()

# send the daily backup to the pair server
import webnotes.defs
if hasattr(webnotes.defs,'ps_host'):
	import ftplib, time

	ftp = ftplib.FTP(webnotes.defs.ps_host, webnotes.defs.ps_login, webnotes.defs.ps_pwd)
	ftp.cwd('pair_backups')
	fname = 'daily-' + time.strftime('%Y-%m-%d') + '.tar.gz'
	f = open('/backups/daily/' + fname, 'rb')
	ftp.storbinary('STOR ' + webnotes.defs.server_prefix + '-' + fname, f)
	ftp.quit()
	
	# delete from local pair directory
	if hasattr(webnotes.defs, 'pair_dir') and len(os.listdir(webnotes.defs.pair_dir)) > 3:
		delete_oldest_file(webnotes.defs.pair_dir)