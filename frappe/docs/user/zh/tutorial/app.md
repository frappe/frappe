# What is an Application

An Application in Frappé is just a standard Python application. You can structure a Frappé Application the same way you structure a standard Python Application. For deployment, Frappé uses the standard Python Setuptools, so you can easily port and install the application on any machine.

Frappé Framework provides a WSGI interface and for development you can use the built-in Werkzeug server. For implementing in production, we recommend using nginx and gunicorn.

Frappé also has a multi-tenant architecture, grounds up. This means that you can run multiple "sites" in your setup, each could be serving a different set of applications and users. The database for each site is separate.

{next}
