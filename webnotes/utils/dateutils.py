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

import webnotes

user_date_format = None

def user_to_str(date, date_format = None):
	if not date: return date
	
	import datetime
	
	if not date_format:
		if not user_date_format:
			global user_date_format
			user_date_format = webnotes.conn.get_value("Control Panel", None, "date_format")

		date_format = user_date_format
		
	dateformats = {
		'yyyy-mm-dd':'%Y-%m-%d',
		'dd/mm/yyyy':'%d/%m/%Y',
		'mm/dd/yyyy':'%m/%d/%Y',
		'dd-mm-yyyy':'%d-%m-%Y'
	}
	try:
		return datetime.datetime.strptime(date, 
			dateformats[date_format]).strftime('%Y-%m-%d')
	except ValueError, e:
		webnotes.msgprint("Date %s must be in format %s" % (date, date_format), raise_exception=True)


	
