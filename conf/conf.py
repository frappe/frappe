from __future__ import unicode_literals
# app configuration

# database config
db_name = 'yourdbname'
db_password = 'yourdbpassword'

# user attachments stored in
files_path = 'user_files'

# max file attachment size (default 1MB)
max_file_size = 1000000

# user modules - include in sys.path
modules_path = '.'

# generate schema (.txt files)
developer_mode = 0

# clear cache on refresh
auto_cache_clear = 0

# email logs to admin (beta)
admin_email_notification = 0

# user timezone
user_timezone = 'Asia/Calcutta'

# dump backups here
backup_path = '/backups'

# outgoing mail settings
mail_server = None
mail_login = None
mail_password = None
mail_port = None
use_ssl = None

# logging settings
log_file_name = 'logs/error_log.txt'
debug_log_dbs = []
log_level = 'logging.INFO'
log_file_size = 5000
log_file_backup_count = 5

