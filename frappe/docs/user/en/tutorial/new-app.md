# Make a New App

Once the bench is installed, you will see two main folders, `apps` and `sites`. All the applications will be installed in apps.

To make a new application, go to your bench folder and run, `bench new-app {app_name}` and fill in details about the application. This will create a boilerplate application for you.

	$ bench new-app library_management
	App Title (defaut: Lib Mgt): Library Management
	App Description:  App for managing Articles, Members, Memberships and Transactions for Libraries
	App Publisher: Frappé
	App Email: info@frappe.io
	App Icon (default 'octicon octicon-file-directory'): octicon octicon-book
	App Color (default 'grey'): #589494
	App License (default 'MIT'): GNU General Public License

### App Structure

The application will be created in a folder called `library_management` and will have the following structure:

	.
	├── MANIFEST.in
	├── README.md
	├── library_management
	│   ├── __init__.py
	│   ├── config
	│   │   ├── __init__.py
	│   │   └── desktop.py
	│   ├── hooks.py
	│   ├── library_management
	│   │   └── __init__.py
	│   ├── modules.txt
	│   ├── patches.txt
	│   └── templates
	│       ├── __init__.py
	│       ├── generators
	│       │   └── __init__.py
	│       ├── pages
	│       │   └── __init__.py
	│       └── statics
	├── license.txt
	├── requirements.txt
	└── setup.py

1. `config` folder contains application configuration info
1. `desktop.py` is where desktop icons can be added to the Desk
1. `hooks.py` is where integrations with the environment and other applications is mentioned.
1. `library_management` (inner) is a **module** that is bootstrapped. In Frappé, a **module** is where model and controller files reside.
1. `modules.txt` contains list of **modules** in the app. When you create a new module, it is required that you update it in this file.
1. `patches.txt` is where migration patches are written. They are python module references using the dot notation.
1. `templates` is the folder where web view templates are maintained. Templates for **Login** and other standard pages are bootstrapped in frappe.
1. `generators` are where templates for models are maintained, where each model instance has a separte web route, for example a **Blog Post** where each post has its unique web url. In Frappé, the templating engine used is Jinja2
1. `pages` is where single route templates are maintained. For example for a "/blog" type of page.

{next}
