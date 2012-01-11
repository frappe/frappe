# This file contains all the major settings regarding
# You must setup this file before running the application
# There are also settings for multiple files
# You must save this file as "defs.py" to make it live
# =================================================================================

#
# [IMPORTANT] - Please set your default db_name
#
default_db_name = ''
db_password = 'some_password'

#
# map of database names to account names
# if you are running multiple database instances, then you can set "account names" to each database
# account names can be same as db_names - it is only to mask database names for security reasons
# un-comment this if you want to use db_names
#
#db_name_map = {'accountname':'dbname'}

#
# if you are running multiple applications on one server, then you can use this to map a domain name to an
# database name. comment this if you do not want to map domain names
#
#domain_name_map = {'example.com':'dbname'}


#
# Path to your MySQL command account, if not directly "mysql"	
#
mysql_path = ''

#
# Attachment Files Path: This is where attachments are stored. Attachments are not stored in the database
# as they can incease backup sizes.
# It is best to keep this folder outside your www folder so that it is not accessible directly
#
files_path = 'user_files'

#
# Modules path: This is where the module files are stored
# If this is blank, your modules files will be saved in the 'cgi-bin' forder
#
modules_path = ''

#
# Developer Mode: If the developer_mode is set, all updates to DocTypes, Pages and Search Criteria will be
# saved to the modules folder
#
developer_mode = 0

#
# Auto Clear Cache: If set, automatically clears cache on refresh
#

auto_cache_clear = 0

#
# Admin Email Notification: If the admin_email_notification is set, 
# then only sent notification email from the system to admin_email_address
#

admin_email_notification = 0
admin_email_address = 'test@example.com'

#
# Global Send Email: Global email settings, if 1 then only mail will go from the system
#

global_send_email = 1

#
# Time Zone: Useful if your users are across timezones
#
user_timezone = 'Asia/Calcutta'

#
# Default Mail Server Settings
# If mail server settings are not set in the Control Panel, they are picked from here
#
mail_server = None
mail_login = None
mail_password = None
mail_port = None
use_ssl = None

# 
# Email Batching Settings
# Batching of emails is a good idea because sending an email takes a longer time in the middle of a transaction
# and locks the table. If emails are batched, you need to setup cron to call 
# webnotes.utils.email_lib.EmailQueue().flush()
#
batch_emails = 0
# email_queue = 'email_queue.py'

#
# Logging Settings: Log using the python logger
# Error levels (in string): 'login.DEBUG', 'login.INFO', 'login.WARNING', 'logging.ERROR', 'login.CRITICAL'
#
log_file_name = 'logs/error_log.txt'
debug_log_dbs = []
log_level = 'logging.INFO'
log_file_size = 5000
log_file_backup_count = 5

#
# Backup Settings
#

# where the dumps will be stored
backup_path = '/backups'

# where the latest dump will show up so that it can be
# downloaded from the web
backup_link_path = '/var/www/wnframework/backups'

# url to be emailed to the "System Manager" Role to download
# the backup
backup_url = 'http://localhost/backups'

# System TimeZone (should be acceptable by pytz: Recommended format Continent/City)
system_timezone = 'Asia/Kolkata'
