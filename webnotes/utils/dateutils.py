# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
import webnotes.defaults
import datetime
from webnotes.utils import get_datetime

# global values -- used for caching
dateformats = {
	'yyyy-mm-dd': '%Y-%m-%d',
	'mm/dd/yyyy': '%m/%d/%Y',
	'mm-dd-yyyy': '%m-%d-%Y',
	"mm/dd/yy": "%m/%d/%y", 
	'dd-mmm-yyyy': '%d-%b-%Y', # numbers app format
	'dd/mm/yyyy': '%d/%m/%Y',
	'dd-mm-yyyy': '%d-%m-%Y',
	"dd/mm/yy": "%d/%m/%y",
}

def user_to_str(date, date_format=None):
	if not date: return date
	
	if not date_format:
		date_format = get_user_date_format()

	try:
		return datetime.datetime.strptime(date, 
			dateformats[date_format]).strftime('%Y-%m-%d')
	except ValueError, e:
		raise ValueError, "Date %s must be in format %s" % (date, date_format)

def parse_date(date):
	"""tries to parse given date to system's format i.e. yyyy-mm-dd. returns a string"""
	parsed_date = None
	
	# why the sorting? checking should be done in a predictable order
	check_formats = [None] + sorted(dateformats.keys(),
		reverse=not get_user_date_format().startswith("dd"))
		
	for f in check_formats:
		try:
			parsed_date = user_to_str(date, f)
			if parsed_date:
				break
		except ValueError, e:
			pass

	if not parsed_date:
		raise Exception, """Cannot understand date - '%s'.
			Try formatting it like your default format - '%s'""" % \
			(date, get_user_date_format())

	return parsed_date
		
def get_user_date_format():
	if getattr(webnotes.local, "user_date_format", None) is None:
		webnotes.local.user_date_format = webnotes.defaults.get_global_default("date_format")

	return webnotes.local.user_date_format
	
def datetime_in_user_format(date_time):
	if not date_time:
		return ""
	if isinstance(date_time, basestring):
		date_time = get_datetime(date_time)
	from webnotes.utils import formatdate
	return formatdate(date_time.date()) + " " + date_time.strftime("%H:%M")