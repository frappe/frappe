## wnframework

Full-stack web application framework that uses python/mysql on the server side and a tightly integrated client side library. Primarily built for erpnext.

Projects: [erpnext](http://erpnext.org) | [webnotes/erpnext](https://github.com/webnotes/erpnext)

## Setup

To start a new project, in the application root:

1. Set wnframework folder as the `lib` folder.
1. Copy the following files from lib/conf: `index.cgi`, `build.json`, `conf.py`. 
1. Create folders `js`, `css`, `modules`, `modules/startup`. These folders contain the js, css assets and modules folder is where all the new application modules will be created.
1. Update database name/password in conf.py and set modules folder to "modules".
1. Run `$ lib/wnf.py --install dbrootpassword newdbname lib/conf/Framework.sql` to install a fresh database.
1. Create `app.js` containing basic application info (see `lib/conf`)
1. Create empty files `__init__.py` and `event_handlers.py` in `modules/startup`. This is where you write all events (like, onlogin, onlogout etc)
1. Run `$ lib/wnf.py -b` to build js and css assets from `build.json`.
1. Go to the browser and go to your application folder. The admin username is "Administrator" and password is "admin"

enjoy!

## wnf.py

`$ lib/wnf.py --help` for more info

## License

wnframework is freely available to use under the MIT License