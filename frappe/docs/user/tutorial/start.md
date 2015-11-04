# Starting the Bench

Now we can login and check if everything works.

To start the development server, run `bench start`

	$ bench start
	13:58:51 web.1        | started with pid 22135
	13:58:51 worker.1     | started with pid 22136
	13:58:51 workerbeat.1 | started with pid 22137
	13:58:52 web.1        |  * Running on http://0.0.0.0:8000/
	13:58:52 web.1        |  * Restarting with reloader
	13:58:52 workerbeat.1 | [2014-09-17 13:58:52,343: INFO/MainProcess] beat: Starting...

You can now open your browser and go to `http://localhost:8000`. You should see this login page if all goes well:

<img class="screenshot" alt="Login Screen" src="{{url_prefix}}/assets/img/login.png">

Now login as the default user "Administrator"

Login ID: **Administrator**
Password: **admin**

When you login, you should see the "Desk" home page

<img class="screenshot" alt="Desk" src="{{url_prefix}}/assets/img/desk.png">

As you can see, the Frappe basic system comes with a bunch of pre-loaded applications and screens like To Do, Calendar etc. These apps can integrated in your app workflow as we progress.

{next}
