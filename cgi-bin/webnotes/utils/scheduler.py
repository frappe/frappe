"""
Simple Scheduler

This scheduler is used to fire events across multiple databases. A database
master_scheduler is maintained with one event and one log table

Events are added by different databases in the master scheduler using the
`set_event` method and they are executed by the cron.

__main__ will call run

To install:
-----------

python install_lib.py [root] [password] master_scheduler

In cron:
--------

python [path]webnotes/utils/scheduler.py

"""


class Scheduler:
	def connect(self):
		"""
			Connect to the 'master_schduler' database
		"""
		if hasattr(self,'conn'): return
		
		import webnotes.defs, webnotes.db
		
		pwd = webnotes.defs.__dict__.get('scheduler_password')
		if pwd==None: pwd = webnotes.defs.db_password
		
		self.conn = webnotes.db.Database(user='master_scheduler',password=pwd)
		
	def set(self, event, interval, recurring, db_name=None):
		"""
			Add an event to the Event table in the master scheduler
		"""
		self.connect()

		if not db_name:
			import webnotes
			db_name = webnotes.conn.cur_db_name

		self.clear(db_name, event)
		self.conn.sql("""insert into 
			Event (`db_name`, `event`, `interval`, next_execution, recurring) 
			values  (%s, %s, %s, ADDTIME(NOW(), SEC_TO_TIME(%s)), %s)
			""", (webnotes.conn.cur_db_name, event, interval, interval, recurring))

	def get_events(self, db_name=None):
		"""
			Returns list of upcoming events
		"""
		self.connect()
		if not db_name:
			import webnotes
			db_name = webnotes.conn.cur_db_name
			
		return self.conn.sql("select * from Event where db_name=%s", db_name, as_dict=1)


	def get_log(self, db_name=None):
		"""
			Returns log of events
		"""
		self.connect()
		if not db_name:
			import webnotes
			db_name = webnotes.conn.cur_db_name

		return self.conn.sql("select * from EventLog where db_name=%s limit 50", db_name, as_dict=1)

	def clear(self, db_name, event):
		"""
			Clears the event
		"""
		self.connect()
		self.conn.sql("delete from Event where `event`=%s and db_name=%s", (event, db_name))

	def execute(self, db_name, event):
		"""
			Executes event in the specifed db
		"""
		import webnotes, webnotes.defs, webnotes.db

		try:
			webnotes.conn = webnotes.db.Database(user=db_name, password=webnotes.defs.db_password)
			webnotes.session = {'user':'Administrator'}

			module = '.'.join(event.split('.')[:-1])
			method = event.split('.')[-1]
		
			exec 'from %s import %s' % (module, method)
		
			webnotes.conn.begin()
			ret = locals()[method]()
			webnotes.conn.commit()
			webnotes.conn.close()
			
			self.log(db_name, event, ret or 'Ok')
			
		except Exception, e:
			self.log(db_name, event, webnotes.getTraceback())

	def log(self, db_name, event, traceback):
		"""
			Log an event error
		"""
		self.conn.sql("insert into `EventLog`(db_name, event, log, executed_on) values (%s, %s, %s, now())", \
			(db_name, event, traceback))
			
		# delete old logs
		self.conn.sql("delete from EventLog where executed_on < subdate(curdate(), interval 30 day)")

	def run(self):
		"""
			Run scheduled (due) events and reset time for recurring events
		"""
		el = self.conn.sql("""select `db_name`, `event`, `recurring`, `interval`
			from `Event` 
			where next_execution < NOW()""", as_dict=1)
		
		for e in el:
			# execute the event
			self.execute(e['db_name'], e['event'])
			
			# if recurring, update next_execution
			if e['recurring']:
				self.conn.sql("update Event set next_execution = addtime(now(), sec_to_time(%s))", e['interval'])
			
			# else clear
			else:
				self.clear(e['db_name'], e['event'])

def set_event(event, interval=60*60*24, recurring=1):
	"""
		Adds an event to the master scheduler
	"""
	return Scheduler().set(event, interval, recurring)


def cancel_event(event):
	"""
		Cancels an event
	"""
	import webnotes
	return Scheduler().clear(webnotes.conn.cur_db_name, event)

# to be called from cron
if __name__=='__main__':
	import os,sys

	cgi_bin_path = os.path.sep.join(__file__.split(os.path.sep)[:-3])

	sys.path.append(cgi_bin_path)

	import webnotes
	import webnotes.defs
	sys.path.append(getattr(webnotes.defs,'modules_path',None))

	sch = Scheduler()
	sch.connect()
	sch.run()
	