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
"""
Scheduler will call the following events from the module
`startup.schedule_handler`

execute_always
execute_daily
execute_monthly
execute_weekly

The scheduler should be called from a cron job every x minutes (5?) depending
on the need.
"""

import webnotes
def execute():
	"""
	execute jobs
	this method triggers the other scheduler events
	Database connection: Ideally it should be connected from outside, if there is
	no connection, it will connect from defs.py
	"""
	from datetime import datetime
	import webnotes.utils
	
	format = '%Y-%m-%d %H:%M:%S'
	
	if not webnotes.conn:
		webnotes.connect()
	
	out = []

	# if first task of the day execute daily tasks
	nowtime = webnotes.utils.now_datetime()
	last = webnotes.conn.get_global('scheduler_last_event')
	if last:
		last = datetime.strptime(last, format)

		if nowtime.day != last.day:

			out.append('daily:' + trigger('execute_daily'))

			if nowtime.month != last.month:
				out.append('monthly:' + trigger('execute_monthly'))
					
			if nowtime.weekday()==0:
				out.append('weekly:' + trigger('execute_weekly'))
			
		if nowtime.hour != last.hour:
			out.append('hourly:' + trigger('execute_hourly'))

	out.append('all:' + trigger('execute_all'))
	
	webnotes.conn.begin()
	webnotes.conn.set_global('scheduler_last_event', nowtime.strftime(format))
	webnotes.conn.commit()
	
	return '\n'.join(out)
	
def trigger(method):
	"""trigger method in startup.schedule_handler"""
	try:
		import startup.schedule_handlers
		
		if hasattr(startup.schedule_handlers, method):
			webnotes.conn.begin()
			getattr(startup.schedule_handlers, method)()
			webnotes.conn.commit()
			return 'ok'
		
	except Exception, e:
		return log(method)

def log(method):
	"""log error in patch_log"""
	import webnotes
	webnotes.conn.rollback()
	traceback = webnotes.getTraceback()

	import webnotes.utils
	webnotes.conn.begin()
	webnotes.conn.sql("""insert into __SchedulerLog (`timestamp`, method, error) 
		values (%s, %s, %s)""", (webnotes.utils.now_datetime(), method, traceback))
	webnotes.conn.commit()

	return traceback

if __name__=='__main__':
	execute()
