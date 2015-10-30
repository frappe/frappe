# Site Config

Settings for `sites/[site]/site_config.json`

`site_config.json` stores global settings for a particular site and is present in the site directory. Here is a list of properties you can set in `site_config.json`.

Example:

    {
     "db_name": "test_frappe",
     "db_password": "test_frappe",
     "admin_password": "admin",
    }

### Mandatory Settings

- `db_name`: Database Name.
- `db_password`: Database password.

### Optional Settings

- `db_host`: Database host if not `localhost`.
- `admin_password`: Default Password for "Administrator".
- `mute_emails`: Stops email sending if true.
- `deny_multiple_logins`: Stop users from having more than one active session.
- `root_password`: MariaDB root password.

### Defaut Outgoing Email Settings

- `mail_server`: SMTP server hostname.
- `mail_port`: STMP port.
- `use_ssl`: Connect via SSL / TLS.
- `mail_login`: Login id for SMTP server.
- `mail_password`: Password for SMTP server.

### Developer Settings

- `developer_mode`: If developer mode is set, DocType changes are automatically updated in files.
- `disable_website_cache`: Don't cache website pages.
- `logging`: writes logs if **1**, writes queries also if set to **2**.
