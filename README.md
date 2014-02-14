## frappe

Full-stack web application framework that uses Python/MySql on the server side and a tightly integrated client side library. Primarily built for erpnext.

Projects: [erpnext](http://erpnext.org) | [frappe/erpnext](https://github.com/frappe/erpnext)

## Setup

To start a new project, in the application root:

Install:

1. Go to the project folder
1. Install frappe and your app:

		$ git clone git@github.com:frappe/frappe lib
		$ git clone git@github.com:frappe/[your app] app
		$ lib/wnf.py --make_conf
		$ lib/wnf.py --reinstall
		$ lib/wnf.py --build

1. Run development server:

		$ lib/wnf.py --serve

	
enjoy!

## wnf.py

`$ lib/wnf.py --help` for more info

## License

frappe is freely available to use under the MIT License
