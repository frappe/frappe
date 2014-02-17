## frappe

Full-stack web application framework that uses Python/MySql on the server side and a tightly integrated client side library. Primarily built for erpnext.

Projects: [erpnext](http://erpnext.org) | [frappe/erpnext](https://github.com/frappe/erpnext)

## Setup

To start a new project, in the application root:

Install:

1. Go to the project folder
1. Install frappe and your app:

	mkdir bench
	cd bench
	git clone https://github.com/frappe/frappe.git
	git clone https://github.com/frappe/[your_app]
	sudo pip install -e frappe/ erpnext/ your_app/
	mkdir sites
	echo app >> sites/apps.txt
	cd sites
	frappe site.local --install erpnext
	frappe site.local --install_app your_app

1. Run development server:

	cd sites
	frappe site.local --serve
	
enjoy!

## wnf.py

`frappe --help` for more info

## License

frappe is freely available to use under the MIT License
