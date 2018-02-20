# Diagnosing The Scheduler

<!-- markdown -->

If you're experiencing delays in scheduled jobs or they don't seem to run, you can run the several commands to diagnose the issue.

### `bench doctor`

This will output the following in order:
- Scheduler Status per site
- Number of Workers
- Pending Tasks


Desirable output:

	Workers online: 0
	-----None Jobs-----

### `bench --site [site-name] show-pending-jobs`

This will output the following in order:
- Queue
- Tasks within Queue

Desirable output:

	-----Pending Jobs-----


### `bench purge-jobs`

This will remove all pending jobs from all queues