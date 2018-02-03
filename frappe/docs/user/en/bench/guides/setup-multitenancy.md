# Setup Multitenancy

Assuming that you've already got your first site running and you've performed
the [production deployment steps](setup-production.html), this section explains how to host your second
site (and more). Your first site is automatically set as default site. You can
change it with the command,
	
	bench use sitename




Port based multitenancy
-----------------------

You can create a new site and make run it on a different port (while the first
one runs on port 80).

* Switch off DNS based multitenancy (once)

	`bench config dns_multitenant off`

* Create a new site

	`bench new-site site2name`

* Set port

	`bench set-nginx-port site2name 82`

* Re generate nginx config

	`bench setup nginx`

* Reload nginx

	`sudo service nginx reload`


DNS based multitenancy
----------------------

You can name your sites as the hostnames that would resolve to it. Thus, all the sites you add to the bench would run on the same port and will be automatically selected based on the hostname. 

To make a new site under DNS based multitenancy, perform the following steps.

* Switch on DNS based multitenancy (once)
	
	`bench config dns_multitenant on`

* Create a new site

	`bench new-site site2name`

* Re generate nginx config

	`bench setup nginx`

* Reload nginx

	`sudo service nginx reload`
