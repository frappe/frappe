# Setup Production

You can setup the bench for production use by configuring two programs, Supervisor and nginx. If you want to revert your Production Setup to Development Setup refer to [these commands](https://github.com/frappe/bench/wiki/Stopping-Production-and-starting-Development)

####Easy Production Setup
These steps are automated if you run `sudo bench setup production`


####Manual Production Setup
Supervisor
----------

Supervisor makes sure that the process that power the Frappé system keep running
and it restarts them if they happen to crash. You can generate the required
configuration for supervisor using the command `bench setup supervisor`. The
configuration will be available in `config/supervisor.conf` directory. You can
then copy/link this file to the supervisor config directory and reload it for it to
take effect.

eg,

```
bench setup supervisor
sudo ln -s `pwd`/config/supervisor.conf /etc/supervisor/conf.d/frappe-bench.conf
```

Note: For CentOS 7, the extension should be `ini`, thus the command becomes
```
bench setup supervisor
sudo ln -s `pwd`/config/supervisor.conf /etc/supervisor/conf.d/frappe-bench.ini #for CentOS 7 only
```

The bench will also need to restart the processes managed by supervisor when you
update the apps. To automate this, you will have to setup sudoers using the
command, `sudo bench setup sudoers $(whoami)`.

Nginx
-----

Nginx is a web server and we use it to serve static files and proxy rest of the
requests to frappe. You can generate the required configuration for nginx using
the command `bench setup nginx`. The configuration will be available in
`config/nginx.conf` file. You can then copy/link this file to the nginx config
directory and reload it for it to take effect.

eg,

```
bench setup nginx
sudo ln -s `pwd`/config/nginx.conf /etc/nginx/conf.d/frappe-bench.conf
```

Note: When you restart nginx after the configuration change, it might fail if
you have another configuration with server block as default for port 80 (in most
cases for the nginx welcome page). You will have to disable this config.  Most
probable places for it to exist are `/etc/nginx/conf.d/default.conf` and
`/etc/nginx/conf.d/default`.
