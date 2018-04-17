# Migrations

A project often undergoes changes related to database schema during course of
its life. It may also be required patch existing data. Frappe bundles tools to
handle these schenarios.

When you pull updates from any Frappe app (including Frappe), you should run
`bench migrate` to apply schema changes and data migrations if any.

## Schema changes

You can edit a DocType to add, remove or change fields. On saving a DocType,
a JSON file containing the DocType data is added to source tree of your app.
When you add an app to a site, the DocTypes are installed using this JSON file.
For making schema changes, it's required to set `developer_mode` in the
configuration.

On running a sync (`bench migrate`), doctypes in the system are synced to
their latest version from the JSON files in the app.

Note: Fields are soft deleted ie. the columns are not removed from the database
table and however, they will not be visible in the documents. This is done to
avoid any potential data loss situations and to allow you write related data
migrations which might need values from deleted fields.

Note: Frappe doesn't support reverse schema migrations.

## Data Migrations

On introducing data related changes, you might want to run one off scripts to
change existing data to match expectations as per new code.

To add a data migration to your code, you will have to write an `execute`
function to a python module and add it to  `patches.txt` of your app.

It is recommended to make a file with a patch number and name in its path and
add it to a patches package (directory) in your app. You can then add a line
with dotted path to the patch module to `patches.txt`.

The directory structure followed in Frappe is as below


	frappe
	└── patches
		└── 4_0
			└── my_awesome_patch.py

The patch can be added to `patches.txt` by adding a line like

	frappe.patches.4_0.my_awesome_patch

The metadata ie. DocType available in the execute function will be the latest as
per JSON files in the apps. However, you will not be able to access metadata of
any previous states of the system.

#### One off Python statements

You can also add one off python statements in `patches.txt` using the syntax,
	execute:{python statement}

For example,
	execute:frappe.get_doc("User", "Guest").save()

Note: All lines in patches.txt have to be unique. If you want to run a line
twice, you can make it unique by adding a distinct comment.

For Example,

	execute:frappe.installer.make_site_dirs() #2014-02-19
