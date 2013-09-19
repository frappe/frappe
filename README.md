## wnframework

Full-stack web application framework that uses Python/MySql on the server side and a tightly integrated client side library. Primarily built for erpnext.

Projects: [erpnext](http://erpnext.org) | [webnotes/erpnext](https://github.com/webnotes/erpnext)

## Setup

To start a new project, in the application root:

Install:

1. Go to the project folder
1. Install webnotes and your app:

		$ git clone git@github.com:webnotes/wnframework lib
		$ git clone git@github.com:webnotes/[your app] app
		$ lib/wnf.py --make_conf
		$ lib/wnf.py --reinstall
		$ lib/wnf.py --build

1. Setup Apache Conf from `conf/apache.conf`
	- Allow cgi to handle `.py` files
	- Rewrite to make clean urls
	- Note: the document root is the `public` folder in your project folder
	
1. Give ownership of the project folder to apache user (`www-data` or `apache`) to make .pyc files and upload files.

enjoy!

## wnf.py

`$ lib/wnf.py --help` for more info

## License

wnframework is freely available to use under the MIT License