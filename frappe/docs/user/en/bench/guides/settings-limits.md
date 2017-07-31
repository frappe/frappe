# Setting Limits for your Site

Frappé v7 has added support for setting limits and restrictions for your site.
These restrictions are set in the `site_config.json` file inside the site's folder. 

	{
	 "db_name": "xxxxxxxxxx",
	 "db_password": "xxxxxxxxxxxx",
	 "limits": {
	  "emails": 1500,
	  "space": 0.157,
	  "expiry": "2016-07-25",
	  "users": 1
		}
	}

You can set a limit by running:

	bench --site [sitename] set-limit [limit] [value]

You can set multiple limits at the same time, by running 
	
	bench --site [sitename] set-limits --limit [limit] [value] --limit [limit-2] [value-2]

The valid limits you can set are: 

- **users** - Limit on the number of maximum users for a site
- **emails** - Limit on the number of emails sent per month from the site
- **space** - Limit on the maximum space the site can use (GB)
- **email_group** - Limit on the maximum number of members allowed in an Email Group
- **expiry** - Expiry date for the site (YYYY-MM-DD within quotes)

Example:

	bench --site site1.local set-limit users 5

You can check your usage by opening the "Usage Info" page from the toolbar / AwesomeBar. A limit will only show up on the page if it has been set.

<img class="screenshot" alt="Doctype Saved" src="/docs/assets/img/usage_info.png">
