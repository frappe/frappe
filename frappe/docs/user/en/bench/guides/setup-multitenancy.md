Assuming that you've already got your first site running and you've performed
the [production deployment steps](production-setup.html), this section explains how to host your second
site (and more). Your first site is automatically set as default site. You can
change it with the command,
	
	bench use sitename




Port based multitenancy
-----------------------

DNS based multitenancy mode is enabled by default, switch it off using the command
```
	bench config dns_multitenant off
```

You can create a new site and make run it on a different port (while the first
one runs on port 80).

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

* Create a new site

	`bench new-site site2name`

* Re generate nginx config

	`bench setup nginx`

* Reload nginx

	`sudo service nginx reload`