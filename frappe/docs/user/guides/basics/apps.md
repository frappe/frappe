# Frappe Apps

Frappe Apps are Python packages which use the Frappe platform. They can live
anywhere on the [Python
path](https://docs.python.org/2/tutorial/modules.html#the-module-search-path)
and must have an entry in the `apps.txt` file.


### Creating an app

Frappe ships with a boiler plate for a new app. The command `bench make-app
app-name` helps you start a new app by starting an interactive shell.


	% bench make-app sample_app
	App Name: sample_app
	App Title: Sample App
	App Description: This is a sample app.
	App Publisher: Acme Inc.
	App Icon: icon-linux
	App Color: #6DAFC9
	App Email: info@example.com
	App URL: http://example.com
	App License: MIT

The above command would create an app with the following directory structure.

	sample_app
	├── license.txt
	├── MANIFEST.in
	├── README.md
	├── sample_app
	│   ├── __init__.py
	│   ├── sample_app
	│   │   └── __init__.py
	│   ├── config
	│   │   ├── desktop.py
	│   │   └── __init__.py
	│   ├── hooks.py
	│   ├── modules.txt
	│   ├── patches.txt
	│   └── templates
	│       ├── generators
	│       │   └── __init__.py
	│       ├── __init__.py
	│       ├── pages
	│       │   └── __init__.py
	│       └── statics
	└── setup.py

Here, "App Icon" is a font awesome class that you can select from
[http://fortawesome.github.io/Font-Awesome/icons/](http://fortawesome.github.io/Font-Awesome/icons/).

The boiler plate contains just enough files to show your app icon on the [Desk].

### Files in the app

#### `hooks.py`

The	`hooks.py` file defines the metadata of your app and integration points
with other parts of Frappe or Frappe apps. Examples of such parts include task
scheduling or listening to updates to different documents in the system. For
now, it just contains the details you entered during app creation.


	app_name = "sample-app"
	app_title = "Sample App"
	app_publisher = "Acme Inc."
	app_description = "This is a sample app."
	app_icon = "fa-linux"
	app_color = "black"
	app_email = "info@example.com"
	app_url = "http://example.com"
	app_version = 0.0.1

#### `modules.txt`

Modules in Frappe help you organize Documents in Frappe and they are defined in
the `modules.txt` file in your app. It is necessary for every [DocType] to be
attached to a module. By default a module by the name of your app is added.
Also, each module gets an icon on the [Desk]. For example, the [ERPNext] app is
organized in the following modules.

	accounts
	buying
	home
	hr
	manufacturing
	projects
	selling
	setup
	stock
	support
	utilities
	contacts

### Adding app to a site

Once you have an app, whether it's the one you just created or any other you
downloaded, you are required to do the following things.

1. Add to Python path. It is recommend to do this using a package manager called
   [pip]. `pip install -e src/sample_app` would add the `sample_app` in editable
   mode ie. it will be linked to the source from wherefyou install and
   reinstalling everytime you make a change is not required. This method is
   highly recommended if you are developing the app yourself.

   If you just want to use pip can install packages in a variety of other ways.
   TODO: add link

2. Add line with your app name to apps.txt (in your sites directory) as
   explained in [sites](/help/sites)


TODO: Add screenshot

