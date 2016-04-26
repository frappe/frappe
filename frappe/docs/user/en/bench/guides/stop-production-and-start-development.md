Moving back to a Development setup is pretty easy

Change directory to your bench directory

	cd frappe-bench

Remove supervisor and nginx configs

	rm config/supervisor.conf
	rm config/nginx.conf

Stop running services

	sudo service nginx stop
	sudo service supervisord stop
	
Setup procfile again and start bench

	bench setup procfile
	bench start
