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
- `encryption_key`: encryption_key for stored non user passwords.

### Optional Settings

- `admin_password`: Default Password for "Administrator".
- `mute_emails`: Stops email sending if true.
- `deny_multiple_logins`: Stop users from having more than one active session.
- `root_password`: MariaDB root password.

### Remote Database Host Settings
- `db_host`: Database host if not `localhost`.

To connect to a remote database server using ssl, you must first configure the database host to accept SSL connections. An example of how to do this is available at https://www.digitalocean.com/community/tutorials/how-to-configure-ssl-tls-for-mysql-on-ubuntu-16-04. After you do the configuration, set the following three options. All options must be set for Frappé to attempt to connect using SSL.
- `db_ssl_ca`: Full path to the ca.pem file used for connecting to a database host using ssl. Example value is `"/etc/mysql/ssl/ca.pem"`.
- `db_ssl_cert`: Full path to the cert.pem file used for connecting to a database host using ssl. Example value is `"/etc/mysql/ssl/client-cert.pem"`.
- `db_ssl_key`: Full path to the key.pem file used for connecting to a database host using ssl. Example value is `"/etc/mysql/ssl/client-key.pem"`.

### Default Outgoing Email Settings

- `mail_server`: SMTP server hostname.
- `mail_port`: STMP port.
- `use_ssl`: Connect via SSL / TLS.
- `mail_login`: Login id for SMTP server.
- `mail_password`: Password for SMTP server.

### Developer Settings

- `developer_mode`: If developer mode is set, DocType changes are automatically updated in files.
- `disable_website_cache`: Don't cache website pages.
- `logging`: writes logs if **1**, writes queries also if set to **2**.

### Others

- `robots_txt`: Path to robots.txt file to be rendered when going to frappe-site.com/robots.txt
