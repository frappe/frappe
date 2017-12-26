# Manual Setup

Manual Setup
--------------

Install pre-requisites,

* [Python 2.7](https://www.python.org/download/releases/2.7/)
* [MariaDB](https://mariadb.org/)
* [Redis](http://redis.io/topics/quickstart)
* [WKHTMLtoPDF with patched QT](http://wkhtmltopdf.org/downloads.html) (required for pdf generation)

[Installing pre-requisites on OSX](https://github.com/frappe/bench/wiki/Installing-Bench-Pre-requisites-on-MacOSX)

Install bench as a *non root* user,

		git clone https://github.com/frappe/bench bench-repo
		sudo pip install -e bench-repo

Note: Please do not remove the bench directory the above commands will create


Migrating from existing installation
------------------------------------

If want to migrate from ERPNext version 3, follow the instructions [here](https://github.com/frappe/bench/wiki/Migrating-from-ERPNext-version-3)

If want to migrate from the old bench, follow the instructions [here](https://github.com/frappe/bench/wiki/Migrating-from-old-bench)


Basic Usage
===========

* Create a new bench

	The init command will create a bench directory with frappe framework
	installed. It will be setup for periodic backups and auto updates once
	a day.

		bench init frappe-bench && cd frappe-bench

* Add apps

	The get-app command gets and installs frappe apps. Examples:
	
	- [erpnext](https://github.com/frappe/erpnext)
	- [erpnext_shopify](https://github.com/frappe/erpnext_shopify)
	- [paypal_integration](https://github.com/frappe/paypal_integration)
	
	bench get-app erpnext https://github.com/frappe/erpnext

* Add site

	Frappé apps are run by frappe sites and you will have to create at least one
	site. The new-site command allows you to do that.

		bench new-site site1.local

* Start bench

	To start using the bench, use the `bench start` command

		bench start

	To login to Frappé / ERPNext, open your browser and go to `localhost:8000`

	The default user name is "Administrator" and password is what you set when you created the new site.


Setting Up ERPNext
==================

To install ERPNext, simply run:
```
bench install-app erpnext
```

You can now either use `bench start` or [setup the bench for production use](setup-production.html)



