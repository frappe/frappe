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
		last = datetime.strptime(last_event, format)

		if now.day != last.day:

			out.append('daily:' + trigger('execute_daily'))

			if now.month != last.month:
				out.append('monthly:' + trigger('execute_monthly'))
					
			if now.weekday()==0:
				out.append('weekly:' + trigger('execute_weekly'))
			
	out.append('all:' + trigger('execute_all'))
	
	webnotes.conn.set_global('scheduler_last_event', nowtime.strftime(format))
	
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
		webnotes.conn.rollback()
		traceback = webnotes.getTraceback()
		log(method, traceback)
		return traceback
	
def log(method, error):
	"""log error in patch_log"""
	import webnotes.utils
	webnotes.conn.sql("""insert into __SchedulerLog (`timestamp`, method, error) 
		values (%s, %s, %s)""", (webnotes.utils.now_datetime(), method, error))
	
if __name__=='__main__':
	execute()
