## wnframework

Full-stack web application framework that uses Python/MySql on the server side and a tightly integrated client side library. Primarily built for erpnext.

Projects: [erpnext](http://erpnext.org) | [webnotes/erpnext](https://github.com/webnotes/erpnext)

## Setup

To start a new project, in the application root:

Install:

1. Install webnotes and treemapper

		$ git clone git@github.com:webnotes/wnframework lib
		$ git clone git@github.com:webnotes/[your app] app
		$ lib/wnf.py --make_conf
		$ lib/wnf.py --reinstall

1. Setup Apache Conf

enjoy!


#### Export

Before pushing, export install fixtures

	$ lib/wnf.py --export_doclist "Website Settings" - app/startup/website_settings.json
	$ lib/wnf.py --export_doclist "Style Settings" - app/startup/style_settings.json
	$ lib/wnf.py --export_csv "Tree Species" app/startup/Tree_Species.csv
	$ lib/wnf.py --export_csv "Tree Family" app/startup/Tree_Family.csv

## wnf.py

`$ lib/wnf.py --help` for more info

## License

wnframework is freely available to use under the MIT License