# Setting up the Site

Let us create a new site and call it `library`.

*Note: Before you create any new site, you need to activate the Barracuda storage engine on your MariaDB installation.*
*Copy the following default ERPNext database settings into your `my.cnf` file.*

    [mysqld]
    innodb-file-format=barracuda
    innodb-file-per-table=1
    innodb-large-prefix=1
    character-set-client-handshake = FALSE
    character-set-server = utf8mb4
    collation-server = utf8mb4_unicode_ci

    [mysql]
    default-character-set = utf8mb4

You can then install a new site, by the command `bench new-site library`.

This will create a new database and site folder and install `frappe` (which is also an application!) in the new site. The `frappe` application has two built-in modules **Core** and **Website**. The Core module contains the basic models for the application. Frappé is a batteries included framework and comes with a lot of built-in models. These models are called **DocTypes**. More on that later.

	$ bench new-site library
	MySQL root password:
	Installing frappe...
	Updating frappe                     : [========================================]
	Updating country info               : [========================================]
	Set Administrator password:
	Re-enter Administrator password:
	Installing fixtures...
	*** Scheduler is disabled ***

### Site Structure

A new folder called `library` will be created in the `sites` folder. Here is the standard folder structure for a site.

	.
	├── locks
	├── private
	│   └── backups
	├── public
	│   └── files
	└── site_config.json

1. `public/files` is where user uploaded files are stored.
1. `private/backups` is where backups are dumped
1. `site_config.json` is where site level configurations are maintained.

### Setting Default Site

In case you have multiple sites on you bench use `bench use [site_name]` to set the default site.

Example:

	$ bench use library

### Install App

Now let us install our app `library_management` in our site `library`

1. Install library_management in library with: `bench --site [site_name] install-app [app_name]`

Example:

	$ bench --site library install-app library_management

{next}
