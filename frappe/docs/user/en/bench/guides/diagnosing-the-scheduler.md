<!-- markdown -->

If you're experiencing delays in scheduled jobs or they don't seem to run, you can run the several commands to diagnose the issue.

### `bench doctor`

This will output the following in order:
- Worker Status
- Scheduler Status per site
- Pending Tasks
- Timed out locks

Desirable output:

	Workers online: True
	Pending tasks 0
	Timed out locks:


### `bench celery-doctor`

This will output the following in order:
- Queue Status
- Running Tasks

Desirable output:

	Queue Status
	------------
	[
	 {
	  "total": 0
	 }
	]

	Running Tasks
	------------
	{
	 "async@erpnext": [],
	 "longjobs@erpnext": [],
	 "jobs@erpnext": []
	}


### `bench dump-queue-status`

This will output detailed diagnostic information for task queues in JSON

Desirable output:


	[
	 {
	  "total": 0
	 }
	]
	Pending Tasks Queue
	--------------------

