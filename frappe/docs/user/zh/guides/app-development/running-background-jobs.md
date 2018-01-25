# Running Background Jobs

Sometimes you may not want a user request to be executed immediately but added to a queue that will be executed by a background worker. The advantage of doing this is that your web workers remain free to execute other requests and longer jobs do not eat up all of your resources.

From version 7, Frappé uses Python RQ to run background jobs.

To enqueue a job,

	from frappe.jobs.background_jobs import enqueue

	def long_job(arg1, arg2):
		frappe.publish_realtime('msgprint', 'Starting long job...')
		# this job takes a long time to process
		frappe.publish_realtime('msgprint', 'Ending long job...')

	def enqueue_long_job(arg1, args2):
		enqueue('myapp.mymodule.long_job', arg1=arg1, arg2=arg2)

This will enqueue to the queue `default`

other queues are `worker_long` and `worker_short`

#### Called delayed actions on Document objects

You can also called delayed actions on document objects, for example in Stock Reconciliation if there are more than 100 items, it is executed as a background job.

Example: you can call `doc.queue_action('submit')`

Note: This only works for `save`, `submit`, `cancel`

You can also push certain actions to the background if you anticipate the execution is very large.

For example:

	def submit(self):
		if len(self.items) > 100:
			self.queue_action('submit')
		else:
			self._submit()

#### Debugging

If you are on `bench start`

You will see logs in your terminal.

Note: default worker does not auto restart, so you will have to kill bench and start again after you make changes.