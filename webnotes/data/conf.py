# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# DEPRECATED only for reference

from __future__ import unicode_literals
# app configuration

# database config
db_name = '%(db_name)s'
db_password = '%(db_password)s'

# user attachments stored in
files_path = 'public/files'
public_path = 'public'

# max file attachment size (default 1MB)
max_file_size = 1000000

# max email size in bytes
max_email_size = 0

# total pop session timeout in seconds
pop_timeout = 0

# generate schema (.txt files)
developer_mode = 0

# clear cache on refresh
auto_cache_clear = 0

# email logs to admin (beta)
admin_email_notification = 0

# user timezone
user_timezone = 'Asia/Calcutta'

# outgoing mail settings
mail_server = None
mail_login = None
mail_password = None
mail_port = None
use_ssl = None
auto_email_id = None

# logging settings
log_file_name = 'logs/error_log.txt'
debug_log_dbs = []
log_level = 'logging.INFO'
log_file_size = 5000
log_file_backup_count = 5

