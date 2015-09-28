import os
from frappe.utils import get_site_path
from frappe.utils.data import convert_utc_to_user_timezone
import datetime

def get_context(context):
	def get_time(path):
		dt = os.path.getmtime(path)
		return convert_utc_to_user_timezone(datetime.datetime.utcfromtimestamp(dt)).strftime('%Y-%m-%d %H:%M')

	def get_size(path):
		size = os.path.getsize(path)
		if size > 1048576:
			return "{0:.1f}M".format(float(size) / 1048576)
		else:
			return "{0:.1f}K".format(float(size) / 1024)

	path = get_site_path('private', 'backups')
	files = [x for x in os.listdir(path) if os.path.isfile(os.path.join(path, x))]
	files = [('/backups/' + _file,
		get_time(os.path.join(path, _file)),
		get_size(os.path.join(path, _file))) for _file in files]

	return {"files": files}
