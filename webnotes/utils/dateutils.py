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
import webnotes
import datetime

# global values -- used for caching
user_date_format = None
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
	if not user_date_format:
		global user_date_format
		user_date_format = webnotes.conn.get_value("Control Panel", None, "date_format")
	return user_date_format